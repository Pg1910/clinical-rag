"""
Run Case Pipeline

Single-row case processing with SOAP-structured retrieval and summarization.

Usage:
    python -m icu_copilot.pipeline.run_case --csv data.csv --row 123
    python -m icu_copilot.pipeline.run_case --row 123  # Uses indexed data
"""
from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from icu_copilot.logging_conf import setup_logging
from icu_copilot.config import SETTINGS
from icu_copilot.llm.client import OllamaClient, truncate_evidence_list, estimate_tokens
from icu_copilot.llm.json_guard import parse_with_schema
from icu_copilot.llm.soap_prompts import (
    SOAP_EXTRACTION_PROMPT,
    SOAP_SUMMARY_PROMPT,
    SOAP_DIFFERENTIAL_PROMPT,
    SOAP_QA_PROMPT,
    CLARIFYING_QUESTIONS_PROMPT,
    get_missing_slots,
)
from icu_copilot.rag.retrieve import HybridRetriever
from icu_copilot.rag.soap_retrieval import (
    SOAPRetriever,
    SOAPContext,
    EvidencePack,
    generate_soap_queries,
)
from icu_copilot.ingest.ingest_csv import get_row_by_id, ingest_single_row

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# =============================================================================
# OUTPUT SCHEMAS
# =============================================================================

class SOAPFact(BaseModel):
    label: str
    value: str
    evidence_ids: list[str] = Field(default_factory=list)


class SOAPExtraction(BaseModel):
    S: list[SOAPFact] = Field(default_factory=list)
    O: list[SOAPFact] = Field(default_factory=list)
    A: list[SOAPFact] = Field(default_factory=list)
    P: list[SOAPFact] = Field(default_factory=list)


class DifferentialItem(BaseModel):
    diagnosis: str
    confidence: str = "moderate"
    support: list[SOAPFact] = Field(default_factory=list)
    against: list[SOAPFact] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)


class DifferentialOutput(BaseModel):
    differential: list[DifferentialItem] = Field(default_factory=list)


# Evidence limits for speed optimization
MAX_EVIDENCE_S = 10  # Subjective
MAX_EVIDENCE_O = 10  # Objective  
MAX_EVIDENCE_A = 5   # Assessment
MAX_EVIDENCE_P = 5   # Plan
MAX_EVIDENCE_TOTAL = 30


class CaseReport(BaseModel):
    """Complete case report output."""
    row_id: int
    timestamp: str
    soap_context: dict
    soap_summary: str
    differential: list[dict]
    evidence_used: list[str]


# =============================================================================
# CASE PIPELINE
# =============================================================================

class CasePipeline:
    """
    Pipeline for processing a single case with SOAP-structured retrieval.
    """
    
    def __init__(
        self,
        indices_dir: Path,
        csv_path: Path | None = None,
    ):
        self.indices_dir = indices_dir
        self.csv_path = csv_path
        self.llm = OllamaClient()
        
        # Check if indices exist
        if (indices_dir / "faiss.index").exists():
            self.retriever = HybridRetriever(indices_dir)
            self.soap_retriever = SOAPRetriever(self.retriever)
            self.has_index = True
        else:
            self.has_index = False
            logger.warning("No index found. Will use on-the-fly processing.")
    
    def get_row_data(self, row_id: int) -> dict | None:
        """Fetch row data from CSV."""
        if self.csv_path and self.csv_path.exists():
            return get_row_by_id(self.csv_path, row_id)
        return None
    
    def build_soap_context(self, row_id: int, row_data: dict | None = None) -> SOAPContext:
        """
        Build global SOAP context for a case.
        
        Priority:
        1. If row_data is provided, use it directly (most accurate)
        2. If index exists, try to retrieve from index
        3. Raise error if neither is available
        """
        # If we have row_data, always use it directly (it's the ground truth)
        if row_data:
            return self._build_soap_from_row_data(row_data, row_id)
        
        # Fallback to index-based retrieval
        if self.has_index:
            return self.soap_retriever.build_global_soap(row_id=row_id)
        
        raise RuntimeError("No index and no row data provided")
    
    def _build_soap_from_row_data(self, row_data: dict, row_id: int) -> SOAPContext:
        """Build SOAP context directly from row data without index."""
        from icu_copilot.rag.soap_retrieval import SOAPContext, SOAPFact
        
        records = ingest_single_row(row_data, row_id)
        ctx = SOAPContext(row_id=row_id)
        
        for rec in records:
            text = rec.raw_text
            eid = rec.evidence_id
            etype = rec.evidence_type
            
            # Create fact
            if ":" in text and len(text.split(":")) == 2:
                label, value = text.split(":", 1)
                label = label.strip()
                value = value.strip()
            else:
                label = etype
                value = text[:200]
            
            fact = SOAPFact(label=label, value=value, evidence_ids=[eid])
            
            # Route to appropriate section
            if etype == "csv_conv":
                ctx.S.append(fact)
            elif etype == "csv_summary":
                # Classify based on content
                text_lower = text.lower()
                if any(kw in text_lower for kw in ["diagnosis", "problem", "impression"]):
                    ctx.A.append(fact)
                elif any(kw in text_lower for kw in ["plan", "treatment", "recommend"]):
                    ctx.P.append(fact)
                else:
                    ctx.O.append(fact)
            elif etype in ["csv_note", "csv_full_note"]:
                # Check content
                text_lower = text.lower()
                if any(kw in text_lower for kw in ["complaint", "pain", "symptom", "reports"]):
                    ctx.S.append(fact)
                else:
                    ctx.O.append(fact)
        
        # Cap evidence per section for speed
        ctx.S = ctx.S[:MAX_EVIDENCE_S]
        ctx.O = ctx.O[:MAX_EVIDENCE_O]
        ctx.A = ctx.A[:MAX_EVIDENCE_A]
        ctx.P = ctx.P[:MAX_EVIDENCE_P]
        
        return ctx
    
    def retrieve_evidence_packs(
        self,
        row_id: int,
        soap_context: SOAPContext,
    ) -> dict[str, EvidencePack]:
        """
        Build section-specific evidence packs.
        """
        if not self.has_index:
            logger.warning("No index available for retrieval")
            return {}
        
        # Generate queries from context
        queries = {
            "S": " ".join(f.value for f in soap_context.S[:3]) or "chief complaint symptoms",
            "O": " ".join(f.value for f in soap_context.O[:3]) or "labs vitals findings",
            "A": " ".join(f.value for f in soap_context.A[:3]) or "diagnosis assessment",
            "P": "plan treatment recommendation",
        }
        
        return self.soap_retriever.build_all_packs(queries, row_id)
    
    def extract_soap_llm(
        self,
        evidence_text: str,
    ) -> SOAPExtraction:
        """
        Use LLM to extract structured SOAP facts from evidence.
        """
        prompt = SOAP_EXTRACTION_PROMPT.format(evidence=evidence_text)
        logger.info(f"SOAP extraction prompt: {len(prompt)} chars (~{estimate_tokens(prompt)} tokens)")
        
        raw = self.llm.generate(prompt, json_mode=True)
        return parse_with_schema(raw, SOAPExtraction)
    
    def generate_soap_summary(
        self,
        soap_context: SOAPContext,
        evidence_packs: dict[str, EvidencePack],
    ) -> str:
        """
        Generate human-readable SOAP summary.
        """
        # Combine evidence from all packs
        all_evidence = []
        for section, pack in evidence_packs.items():
            all_evidence.extend(pack.evidence[:5])
        
        evidence_text = "\n".join(f"[{e.evidence_id}] {e.text}" for e in all_evidence[:15])
        
        prompt = SOAP_SUMMARY_PROMPT.format(
            soap_context=soap_context.to_json(),
            evidence=evidence_text,
        )
        
        logger.info(f"SOAP summary prompt: {len(prompt)} chars (~{estimate_tokens(prompt)} tokens)")
        
        return self.llm.generate(prompt, json_mode=False).strip()
    
    def generate_differential(
        self,
        soap_context: SOAPContext,
        evidence_packs: dict[str, EvidencePack],
    ) -> DifferentialOutput:
        """
        Generate differential diagnosis with evidence linkage.
        """
        # Use A and O packs primarily
        a_evidence = evidence_packs.get("A", EvidencePack(section="A")).evidence[:6]
        o_evidence = evidence_packs.get("O", EvidencePack(section="O")).evidence[:4]
        
        evidence_text = "\n".join(
            f"[{e.evidence_id}] {e.text}" 
            for e in (a_evidence + o_evidence)
        )
        
        prompt = SOAP_DIFFERENTIAL_PROMPT.format(
            soap_context=soap_context.to_json(),
            evidence=evidence_text,
        )
        
        logger.info(f"Differential prompt: {len(prompt)} chars (~{estimate_tokens(prompt)} tokens)")
        
        raw = self.llm.generate(prompt, json_mode=True)
        return parse_with_schema(raw, DifferentialOutput)
    
    def generate_clarifying_questions(
        self,
        soap_context: SOAPContext,
    ) -> list[str]:
        """
        Generate clarifying questions based on missing information.
        """
        missing = get_missing_slots(soap_context.to_dict())
        
        if not missing:
            return ["All key information slots appear to be filled."]
        
        missing_str = "\n".join(
            f"- {section}: {', '.join(slots)}"
            for section, slots in missing.items()
        )
        
        prompt = CLARIFYING_QUESTIONS_PROMPT.format(
            soap_context=soap_context.to_json(),
            missing_slots=missing_str,
        )
        
        logger.info(f"Questions prompt: {len(prompt)} chars (~{estimate_tokens(prompt)} tokens)")
        
        response = self.llm.generate(prompt, json_mode=False).strip()
        
        # Parse numbered list
        questions = []
        for line in response.split("\n"):
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith("-")):
                # Remove leading number/bullet
                clean = line.lstrip("0123456789.-) ").strip()
                if clean:
                    questions.append(clean)
        
        return questions or [response]
    
    def run(self, row_id: int) -> CaseReport:
        """
        Execute full case pipeline.
        """
        logger.info(f"Starting case pipeline for row_id={row_id}")
        
        # 1. Get row data if available
        row_data = self.get_row_data(row_id) if self.csv_path else None
        
        # 2. Build global SOAP context
        logger.info("Building SOAP context...")
        soap_context = self.build_soap_context(row_id, row_data)
        logger.info(f"SOAP context: S={len(soap_context.S)}, O={len(soap_context.O)}, A={len(soap_context.A)}, P={len(soap_context.P)}")
        
        # 3. Retrieve section evidence packs
        logger.info("Retrieving evidence packs...")
        evidence_packs = self.retrieve_evidence_packs(row_id, soap_context)
        
        # 4. Generate SOAP summary (LLM call 1)
        logger.info("Generating SOAP summary...")
        soap_summary = self.generate_soap_summary(soap_context, evidence_packs)
        
        # 5. Generate differential (LLM call 2)
        logger.info("Generating differential diagnosis...")
        differential = self.generate_differential(soap_context, evidence_packs)
        
        # NOTE: Clarifying questions removed for speed optimization
        
        # 6. Collect all evidence used
        evidence_used = set()
        for section, pack in evidence_packs.items():
            for e in pack.evidence:
                evidence_used.add(e.evidence_id)
        for section in ["S", "O", "A", "P"]:
            for fact in getattr(soap_context, section):
                evidence_used.update(fact.evidence_ids)
        
        # 7. Compose report
        report = CaseReport(
            row_id=row_id,
            timestamp=datetime.now().isoformat(),
            soap_context=soap_context.to_dict(),
            soap_summary=soap_summary,
            differential=[d.model_dump() for d in differential.differential],
            evidence_used=sorted(evidence_used),
        )
        
        return report
    
    def format_text_output(self, report: CaseReport) -> str:
        """Format report as readable text."""
        lines = []
        
        lines.append("=" * 80)
        lines.append(f"CLINICAL CASE REPORT - Row ID: {report.row_id}")
        lines.append(f"Generated: {report.timestamp}")
        lines.append("=" * 80)
        lines.append("")
        
        # SOAP Summary
        lines.append("─" * 80)
        lines.append("SOAP SUMMARY")
        lines.append("─" * 80)
        lines.append(report.soap_summary)
        lines.append("")
        
        # Differential
        lines.append("─" * 80)
        lines.append("DIFFERENTIAL DIAGNOSIS")
        lines.append("─" * 80)
        for i, dx in enumerate(report.differential, 1):
            lines.append(f"\n{i}. {dx['diagnosis']} ({dx['confidence']} confidence)")
            if dx.get('support'):
                lines.append("   Supporting evidence:")
                for s in dx['support'][:3]:
                    lines.append(f"   - {s['label']}: {s['value']} [{', '.join(s['evidence_ids'])}]")
            if dx.get('missing'):
                lines.append(f"   Missing: {', '.join(dx['missing'][:3])}")
        lines.append("")
        
        # Evidence trail
        lines.append("─" * 80)
        lines.append(f"EVIDENCE USED: {len(report.evidence_used)} items")
        lines.append("─" * 80)
        lines.append(", ".join(report.evidence_used[:20]))
        if len(report.evidence_used) > 20:
            lines.append(f"... and {len(report.evidence_used) - 20} more")
        lines.append("")
        
        lines.append("=" * 80)
        lines.append("END OF REPORT")
        lines.append("=" * 80)
        
        return "\n".join(lines)


# =============================================================================
# CLI ENTRYPOINT
# =============================================================================

def main() -> None:
    setup_logging(logging.INFO)
    
    parser = argparse.ArgumentParser(
        description="Process a single case with SOAP-structured summarization",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python -m icu_copilot.pipeline.run_case --row 123
    python -m icu_copilot.pipeline.run_case --csv data.csv --row 123
    python -m icu_copilot.pipeline.run_case --row 123 --out reports/
        """
    )
    parser.add_argument("--row", type=int, required=True, help="Row ID to process")
    parser.add_argument("--csv", type=Path, help="Path to CSV file (optional)")
    parser.add_argument("--out", type=Path, help="Output directory (default: data/processed/runs/)")
    
    args = parser.parse_args()
    
    root = Path(__file__).resolve().parents[3]
    indices_dir = root / "data" / "indices"
    output_dir = args.out or (root / "data" / "processed" / "runs")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Run pipeline
    pipeline = CasePipeline(
        indices_dir=indices_dir,
        csv_path=args.csv,
    )
    
    report = pipeline.run(args.row)
    
    # Save outputs
    case_dir = output_dir / f"case_{args.row}"
    case_dir.mkdir(parents=True, exist_ok=True)
    
    # JSON output
    json_path = case_dir / "report.json"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    
    # Text output
    text_output = pipeline.format_text_output(report)
    text_path = case_dir / "report.txt"
    text_path.write_text(text_output, encoding="utf-8")
    
    # Print to console
    print(text_output)
    
    logger.info("=" * 50)
    logger.info("CASE PIPELINE COMPLETE")
    logger.info(f"Row ID: {args.row}")
    logger.info(f"Output: {case_dir}")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
