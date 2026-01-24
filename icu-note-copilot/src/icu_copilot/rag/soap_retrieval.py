"""
SOAP Retrieval Module

Implements section-aware retrieval for SOAP (Subjective, Objective, Assessment, Plan) notes:
- Global SOAP context from summary_json
- Local evidence packs with section-specific reranking
- Prefix-based filtering (CS_/CN_/CF_/CV_)
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from icu_copilot.rag.retrieve import HybridRetriever, RetrievalResult
from icu_copilot.config import SETTINGS

logger = logging.getLogger(__name__)


# =============================================================================
# TYPE DEFINITIONS
# =============================================================================

SOAPSection = Literal["S", "O", "A", "P"]

EVIDENCE_PREFIX_MAP = {
    "csv_summary": "CS",
    "csv_note": "CN",
    "csv_full_note": "CF",
    "csv_conv": "CV",
    # Legacy types
    "narrative": "N",
    "lab": "L",
    "monitor": "M",
    "domain": "D",
    "codebook": "C",
    "flowsheet": "F",
}


@dataclass
class SOAPFact:
    """A single SOAP fact with evidence linkage."""
    label: str
    value: str
    evidence_ids: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {"label": self.label, "value": self.value, "evidence_ids": self.evidence_ids}


@dataclass
class SOAPContext:
    """Global SOAP context structure."""
    S: list[SOAPFact] = field(default_factory=list)  # Subjective
    O: list[SOAPFact] = field(default_factory=list)  # Objective
    A: list[SOAPFact] = field(default_factory=list)  # Assessment
    P: list[SOAPFact] = field(default_factory=list)  # Plan
    row_id: int | None = None
    
    def to_dict(self) -> dict:
        return {
            "S": [f.to_dict() for f in self.S],
            "O": [f.to_dict() for f in self.O],
            "A": [f.to_dict() for f in self.A],
            "P": [f.to_dict() for f in self.P],
            "row_id": self.row_id,
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


@dataclass
class EvidencePack:
    """A collection of evidence for a specific SOAP section."""
    section: SOAPSection
    evidence: list[RetrievalResult] = field(default_factory=list)
    
    def to_text(self, max_chars: int = 3000) -> str:
        """Format as text for LLM prompt."""
        lines = []
        total = 0
        for e in self.evidence:
            line = f"[{e.evidence_id}] {e.text}"
            if total + len(line) > max_chars:
                lines.append("[... truncated ...]")
                break
            lines.append(line)
            total += len(line)
        return "\n".join(lines)


# =============================================================================
# SECTION-AWARE RERANKING
# =============================================================================

# Keywords for section-specific boosting
SECTION_KEYWORDS = {
    "S": {  # Subjective - symptoms, complaints, history
        "boost": [
            "pain", "fell", "fall", "hurt", "ache", "cannot", "unable",
            "worse", "better", "duration", "started", "began", "feeling",
            "complains", "reports", "states", "denies", "history",
            "symptom", "complaint", "concern", "worried", "noticed",
        ],
        "boost_prefixes": ["CV", "CN"],  # Prioritize conversation and notes
    },
    "O": {  # Objective - measurements, labs, vitals, exam findings
        "boost": [
            "mg/dl", "mmol", "bpm", "mmhg", "%", "mg", "ml", "kg",
            "temperature", "pulse", "bp", "resp", "spo2", "hr",
            "lab", "vital", "exam", "finding", "observed", "measured",
            "elevated", "decreased", "normal", "abnormal", "positive", "negative",
        ],
        "boost_prefixes": ["CS", "L", "M"],  # Summary facts, labs, monitors
    },
    "A": {  # Assessment - diagnoses, impressions, problem list
        "boost": [
            "diagnosis", "diagnosed", "impression", "assessment", "problem",
            "condition", "disorder", "syndrome", "disease", "likely",
            "probable", "suspect", "differential", "rule out", "consistent with",
            "secondary to", "due to", "caused by", "etiology",
        ],
        "boost_prefixes": ["CS", "CF", "N"],  # Summary, full notes, narratives
    },
    "P": {  # Plan - treatments, orders, follow-up
        "boost": [
            "plan", "order", "prescribe", "recommend", "schedule",
            "follow-up", "refer", "consult", "monitor", "continue",
            "start", "stop", "increase", "decrease", "change",
            "treatment", "therapy", "medication", "procedure",
        ],
        "boost_prefixes": ["CS", "CN"],  # Summary and notes
    },
}


def compute_section_score(
    result: RetrievalResult,
    section: SOAPSection,
    base_score: float
) -> float:
    """
    Compute section-adjusted score with boosting and penalties.
    """
    config = SECTION_KEYWORDS.get(section, {})
    boost_keywords = config.get("boost", [])
    boost_prefixes = config.get("boost_prefixes", [])
    
    score = base_score
    text_lower = result.text.lower()
    eid = result.evidence_id
    
    # Prefix boost (strongest signal)
    prefix = eid.split("_")[0] if "_" in eid else eid[0]
    if prefix in boost_prefixes:
        score *= 1.3
    
    # Keyword boost
    keyword_hits = sum(1 for kw in boost_keywords if kw in text_lower)
    if keyword_hits > 0:
        score *= (1.0 + 0.05 * min(keyword_hits, 5))  # Up to 25% boost
    
    # Numeric density boost for Objective
    if section == "O":
        num_count = len(re.findall(r'\d+\.?\d*', result.text))
        if num_count >= 3:
            score *= 1.2
    
    # Penalize domain/codebook docs leaking into patient facts
    if prefix in ["D", "C"] and section in ["S", "O"]:
        score *= 0.5  # Heavy penalty
    
    return score


def rerank_for_section(
    results: list[RetrievalResult],
    section: SOAPSection,
    top_k: int = 10
) -> list[RetrievalResult]:
    """
    Rerank results for a specific SOAP section.
    """
    scored = [
        (r, compute_section_score(r, section, r.score))
        for r in results
    ]
    scored.sort(key=lambda x: x[1], reverse=True)
    
    # Reconstruct with new scores
    return [
        RetrievalResult(
            evidence_id=r.evidence_id,
            score=new_score,
            text=r.text
        )
        for r, new_score in scored[:top_k]
    ]


# =============================================================================
# SOAP RETRIEVER
# =============================================================================

class SOAPRetriever:
    """
    Section-aware retriever for SOAP-structured clinical notes.
    """
    
    def __init__(self, retriever: HybridRetriever):
        self.retriever = retriever
        self.store = retriever.store
    
    def filter_by_prefix(
        self,
        results: list[RetrievalResult],
        allowed_prefixes: list[str] | None = None,
        blocked_prefixes: list[str] | None = None,
    ) -> list[RetrievalResult]:
        """Filter results by evidence ID prefix."""
        filtered = []
        for r in results:
            prefix = r.evidence_id.split("_")[0] if "_" in r.evidence_id else r.evidence_id[0]
            
            if allowed_prefixes and prefix not in allowed_prefixes:
                continue
            if blocked_prefixes and prefix in blocked_prefixes:
                continue
            
            filtered.append(r)
        
        return filtered
    
    def filter_by_row(
        self,
        results: list[RetrievalResult],
        row_id: int
    ) -> list[RetrievalResult]:
        """Filter results to only include evidence from a specific row."""
        filtered = []
        for r in results:
            # Parse row_id from evidence_id (format: XX_rowid_chunkid)
            parts = r.evidence_id.split("_")
            if len(parts) >= 2:
                try:
                    eid_row = int(parts[1])
                    if eid_row == row_id:
                        filtered.append(r)
                except ValueError:
                    pass
            else:
                # Legacy format, include all
                filtered.append(r)
        
        return filtered
    
    # =========================================================================
    # GLOBAL SOAP CONTEXT
    # =========================================================================
    
    def build_global_soap(
        self,
        row_id: int | None = None,
        summary_evidence: list[RetrievalResult] | None = None,
    ) -> SOAPContext:
        """
        Build global SOAP context from summary_json facts.
        
        If summary_evidence is not provided, retrieves CS_ prefixed evidence.
        """
        ctx = SOAPContext(row_id=row_id)
        
        # Get summary evidence
        if summary_evidence is None:
            # Retrieve all CS_ evidence for this row
            all_results = self.retriever.hybrid_search(
                "patient summary diagnosis treatment history", top_k=50
            )
            summary_evidence = self.filter_by_prefix(all_results, allowed_prefixes=["CS"])
            if row_id is not None:
                summary_evidence = self.filter_by_row(summary_evidence, row_id)
        
        # Classify facts into SOAP sections based on content
        for ev in summary_evidence:
            text = ev.text.lower()
            eid = ev.evidence_id
            
            # Extract label:value if present
            if ":" in ev.text:
                parts = ev.text.split(":", 1)
                label = parts[0].strip()
                value = parts[1].strip() if len(parts) > 1 else ""
            else:
                label = "fact"
                value = ev.text
            
            fact = SOAPFact(label=label, value=value, evidence_ids=[eid])
            
            # Classify based on content
            if any(kw in text for kw in ["complaint", "symptom", "history", "pain", "duration", "patient reports"]):
                ctx.S.append(fact)
            elif any(kw in text for kw in ["lab", "vital", "exam", "finding", "level", "mg", "mmol", "bpm"]):
                ctx.O.append(fact)
            elif any(kw in text for kw in ["diagnosis", "problem", "condition", "impression", "assessment"]):
                ctx.A.append(fact)
            elif any(kw in text for kw in ["plan", "recommend", "order", "follow", "treatment", "prescribe"]):
                ctx.P.append(fact)
            else:
                # Default to Objective for summary facts
                ctx.O.append(fact)
        
        return ctx
    
    def build_global_soap_from_row(
        self,
        row_data: dict,
        row_id: int
    ) -> SOAPContext:
        """
        Build global SOAP directly from row data (bypassing index).
        Used for on-the-fly processing without full indexing.
        """
        from icu_copilot.ingest.ingest_csv import ingest_single_row
        
        ctx = SOAPContext(row_id=row_id)
        records = ingest_single_row(row_data, row_id)
        
        # Separate by type
        summary_records = [r for r in records if r.evidence_type == "csv_summary"]
        conv_records = [r for r in records if r.evidence_type == "csv_conv"]
        note_records = [r for r in records if r.evidence_type == "csv_note"]
        
        # Build S from conversation
        for rec in conv_records[:3]:  # First few turns
            text = rec.raw_text
            if any(kw in text.lower() for kw in ["pain", "complaint", "symptom", "fell", "hurt"]):
                ctx.S.append(SOAPFact(
                    label="chief_complaint",
                    value=text[:200],
                    evidence_ids=[rec.evidence_id]
                ))
        
        # Build from summary_json
        for rec in summary_records:
            text = rec.raw_text.lower()
            meta = rec.metadata
            label = meta.get("key", "fact")
            value = meta.get("value", rec.raw_text)
            
            fact = SOAPFact(label=label, value=value, evidence_ids=[rec.evidence_id])
            
            if any(kw in text for kw in ["complaint", "symptom", "history"]):
                ctx.S.append(fact)
            elif any(kw in text for kw in ["lab", "vital", "finding", "exam"]):
                ctx.O.append(fact)
            elif any(kw in text for kw in ["diagnosis", "problem", "impression"]):
                ctx.A.append(fact)
            elif any(kw in text for kw in ["plan", "treatment", "recommend"]):
                ctx.P.append(fact)
            else:
                ctx.O.append(fact)
        
        # Add note context to S if no conversation
        if not ctx.S and note_records:
            for rec in note_records[:2]:
                ctx.S.append(SOAPFact(
                    label="note",
                    value=rec.raw_text[:300],
                    evidence_ids=[rec.evidence_id]
                ))
        
        return ctx
    
    # =========================================================================
    # LOCAL EVIDENCE PACKS
    # =========================================================================
    
    def build_section_pack(
        self,
        section: SOAPSection,
        query: str,
        row_id: int | None = None,
        top_k: int = 10,
    ) -> EvidencePack:
        """
        Build evidence pack for a specific SOAP section.
        Uses section-aware queries and reranking.
        """
        # Expand query with section-specific terms
        section_terms = " ".join(SECTION_KEYWORDS.get(section, {}).get("boost", [])[:5])
        expanded_query = f"{query} {section_terms}"
        
        # Retrieve wide
        results = self.retriever.hybrid_search(expanded_query, top_k=top_k * 3)
        
        # Filter by row if specified
        if row_id is not None:
            results = self.filter_by_row(results, row_id)
        
        # Block domain/codebook for S and O sections (patient facts only)
        if section in ["S", "O"]:
            results = self.filter_by_prefix(results, blocked_prefixes=["D", "C"])
        
        # Section-aware reranking
        reranked = rerank_for_section(results, section, top_k=top_k)
        
        return EvidencePack(section=section, evidence=reranked)
    
    def build_subjective_pack(
        self,
        query: str = "chief complaint symptoms history duration",
        row_id: int | None = None,
        top_k: int = 8,
    ) -> EvidencePack:
        """Build Subjective evidence pack (conversation + notes)."""
        pack = self.build_section_pack("S", query, row_id, top_k)
        
        # Boost conversation evidence
        pack.evidence = self.filter_by_prefix(
            pack.evidence, 
            allowed_prefixes=["CV", "CN", "N"]  # Conversation, notes, narratives
        ) or pack.evidence
        
        return pack
    
    def build_objective_pack(
        self,
        query: str = "labs vitals exam findings measurements",
        row_id: int | None = None,
        top_k: int = 10,
    ) -> EvidencePack:
        """Build Objective evidence pack (labs, monitors, exam findings)."""
        pack = self.build_section_pack("O", query, row_id, top_k)
        
        # Prefer structured data
        preferred = self.filter_by_prefix(
            pack.evidence,
            allowed_prefixes=["CS", "L", "M", "CF"]  # Summary, labs, monitors, full notes
        )
        
        return EvidencePack(section="O", evidence=preferred or pack.evidence)
    
    def build_assessment_pack(
        self,
        query: str = "diagnosis impression problem differential",
        row_id: int | None = None,
        top_k: int = 8,
    ) -> EvidencePack:
        """Build Assessment evidence pack (diagnoses, problems)."""
        pack = self.build_section_pack("A", query, row_id, top_k)
        return pack
    
    def build_plan_pack(
        self,
        missing_info: list[str] | None = None,
        row_id: int | None = None,
    ) -> EvidencePack:
        """
        Build Plan evidence pack.
        Plan is often generated from missing slots rather than retrieved.
        """
        if missing_info:
            # Generate clarifying questions template
            plan_facts = [
                RetrievalResult(
                    evidence_id="PLAN_TEMPLATE",
                    score=1.0,
                    text=f"Information needed: {', '.join(missing_info)}"
                )
            ]
            return EvidencePack(section="P", evidence=plan_facts)
        
        # Otherwise retrieve plan-related content
        return self.build_section_pack(
            "P",
            "plan treatment recommendation follow-up orders",
            row_id,
            top_k=5
        )
    
    # =========================================================================
    # FULL EVIDENCE BUNDLE
    # =========================================================================
    
    def build_all_packs(
        self,
        queries: dict[SOAPSection, str] | None = None,
        row_id: int | None = None,
    ) -> dict[SOAPSection, EvidencePack]:
        """
        Build all SOAP evidence packs.
        """
        default_queries = {
            "S": "chief complaint symptoms history duration onset",
            "O": "labs vitals exam findings measurements objective",
            "A": "diagnosis assessment impression problem differential",
            "P": "plan treatment recommendation orders follow-up",
        }
        
        queries = queries or default_queries
        
        return {
            "S": self.build_subjective_pack(queries.get("S", default_queries["S"]), row_id),
            "O": self.build_objective_pack(queries.get("O", default_queries["O"]), row_id),
            "A": self.build_assessment_pack(queries.get("A", default_queries["A"]), row_id),
            "P": self.build_plan_pack(row_id=row_id),
        }


# =============================================================================
# QUERY GENERATION FROM SUMMARY JSON
# =============================================================================

def generate_soap_queries(summary_json: dict) -> dict[SOAPSection, str]:
    """
    Generate section-specific queries from summary_json structure.
    """
    queries: dict[SOAPSection, str] = {}
    
    def extract_terms(obj: dict | list, keys: list[str]) -> list[str]:
        """Extract values matching certain keys."""
        terms = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                if any(key in k.lower() for key in keys):
                    if isinstance(v, str):
                        terms.append(v[:100])
                    elif isinstance(v, list):
                        terms.extend(str(x)[:50] for x in v[:3])
                elif isinstance(v, (dict, list)):
                    terms.extend(extract_terms(v, keys))
        elif isinstance(obj, list):
            for item in obj:
                if isinstance(item, (dict, list)):
                    terms.extend(extract_terms(item, keys))
        return terms
    
    # S queries from symptom/complaint fields
    s_terms = extract_terms(summary_json, ["complaint", "symptom", "history", "present", "onset", "duration"])
    queries["S"] = " ".join(s_terms[:5]) if s_terms else "chief complaint symptoms history"
    
    # O queries from objective fields
    o_terms = extract_terms(summary_json, ["lab", "vital", "exam", "finding", "physical", "objective"])
    queries["O"] = " ".join(o_terms[:5]) if o_terms else "labs vitals exam findings"
    
    # A queries from diagnosis/assessment fields
    a_terms = extract_terms(summary_json, ["diagnosis", "assessment", "impression", "problem", "condition"])
    queries["A"] = " ".join(a_terms[:5]) if a_terms else "diagnosis assessment impression"
    
    # P queries from plan fields
    p_terms = extract_terms(summary_json, ["plan", "treatment", "recommend", "order", "follow"])
    queries["P"] = " ".join(p_terms[:5]) if p_terms else "plan treatment recommendation"
    
    return queries
