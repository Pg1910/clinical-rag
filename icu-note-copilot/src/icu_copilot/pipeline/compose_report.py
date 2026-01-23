from __future__ import annotations
import json
import logging
from pathlib import Path
from icu_copilot.ingest.schemas import (
    ConjoinedReport, 
    PatientState, 
    SummaryOutput, 
    DifferentialOutput,
    ICUStructuredSummary,
    ClarifyingQuestion,
    ActionItem,
)
from icu_copilot.llm.client import OllamaClient, truncate_evidence_list, estimate_tokens
from icu_copilot.llm.json_guard import parse_with_schema
from icu_copilot.llm.prompts import REPORT_COMPOSE_MIN_PROMPT, ICU_SUMMARY_TEMPLATE_PROMPT
from icu_copilot.llm.question_templates import QUESTION_TEMPLATES
from icu_copilot.rag.retrieve import HybridRetriever

logger = logging.getLogger(__name__)


def generate_deterministic_questions(
    differential: DifferentialOutput,
    evidence_ids: list[str],
) -> list[ClarifyingQuestion]:
    """
    Generate clarifying questions deterministically based on differential 'missing' items.
    This is a fallback when LLM doesn't generate questions.
    """
    questions = []
    
    for dx in differential.differential:
        for missing in dx.missing[:2]:  # Max 2 per dx
            # Find related evidence IDs from support
            related_eids = []
            for s in dx.support[:2]:
                related_eids.extend(s.evidence_ids[:1])
            
            if not related_eids:
                related_eids = evidence_ids[:1]
            
            questions.append(ClarifyingQuestion(
                question=missing if missing.endswith("?") else f"{missing}?",
                rationale=f"Needed to confirm or rule out {dx.diagnosis}",
                evidence_ids=related_eids,
                priority="high" if dx.confidence != "high" else "medium",
            ))
    
    return questions[:5]  # Max 5 questions


def generate_deterministic_actions(
    differential: DifferentialOutput,
) -> list[ActionItem]:
    """
    Generate action items deterministically based on differential.
    """
    actions = []
    
    # Check for coagulopathy -> suggest coag panel review
    for dx in differential.differential:
        if "coagul" in dx.diagnosis.lower() or "dic" in dx.diagnosis.lower():
            eids = []
            for s in dx.support:
                eids.extend(s.evidence_ids)
            actions.append(ActionItem(
                item="Review coagulation panel trend (PT/PTT/INR/fibrinogen)",
                rationale="Coagulopathy identified; trending needed",
                evidence_ids=list(set(eids))[:3],
                priority="high",
            ))
            break
    
    # Check for sepsis -> suggest culture review
    for dx in differential.differential:
        if "sepsis" in dx.diagnosis.lower():
            eids = []
            for s in dx.support:
                eids.extend(s.evidence_ids)
            actions.append(ActionItem(
                item="Review blood culture results and antibiotic coverage",
                rationale="Sepsis identified; culture guidance needed",
                evidence_ids=list(set(eids))[:3],
                priority="high",
            ))
            break
    
    return actions[:3]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_evidence_snippets(retriever: HybridRetriever, top_k: int = 8) -> str:
    """Get top N/L/M evidence snippets for context."""
    # Query for key clinical terms
    results = retriever.hybrid_search(
        "sepsis liver failure coagulopathy ARDS BUN PT PTT Kasai", 
        top_k=top_k * 2
    )
    
    # Filter to N/L/M only
    filtered = [r for r in results if r.evidence_id.startswith(("N", "L", "M"))][:top_k]
    
    # Build compact snippets
    snippets = []
    for r in filtered:
        text = r.text[:150] if len(r.text) > 150 else r.text
        snippets.append(f"[{r.evidence_id}] {text}")
    
    return "\n".join(snippets)


def format_icu_summary_with_llm(
    icu_summary: ICUStructuredSummary, 
    llm: OllamaClient
) -> SummaryOutput:
    """
    Use LLM to format ICU structured summary into professional clinical narrative.
    Falls back to deterministic if LLM fails.
    """
    # Convert ICU summary to flat bullets for template
    bullets = []
    
    for b in icu_summary.patient_info:
        bullets.append({"text": f"Patient: {b.text}", "evidence_ids": b.evidence_ids})
    
    if icu_summary.primary_problems:
        problems = ", ".join([p.text for p in icu_summary.primary_problems])
        all_eids = []
        for p in icu_summary.primary_problems:
            all_eids.extend(p.evidence_ids)
        bullets.append({"text": f"Primary problems: {problems}", "evidence_ids": list(set(all_eids))})
    
    for section_name, section_bullets in [
        ("Hepatic", icu_summary.hepatic),
        ("Infectious", icu_summary.infectious),
        ("Respiratory", icu_summary.respiratory),
        ("Coagulation", icu_summary.hematology_coag),
        ("Renal", icu_summary.renal),
    ]:
        if section_bullets:
            text = "; ".join([b.text for b in section_bullets])
            all_eids = []
            for b in section_bullets:
                all_eids.extend(b.evidence_ids)
            bullets.append({"text": f"{section_name}: {text}", "evidence_ids": list(set(all_eids))})
    
    input_json = json.dumps({"summary": bullets}, indent=2)
    
    # Check if we should use LLM
    if estimate_tokens(input_json) > 1500:
        logger.warning("Summary too large for LLM formatting, using direct conversion")
        from icu_copilot.ingest.schemas import SummaryBullet
        return SummaryOutput(summary=[SummaryBullet(text=b["text"], evidence_ids=b["evidence_ids"]) for b in bullets])
    
    prompt = ICU_SUMMARY_TEMPLATE_PROMPT.format(input_summary_json=input_json)
    
    try:
        raw = llm.generate(prompt, json_mode=True)
        return parse_with_schema(raw, SummaryOutput)
    except Exception as e:
        logger.warning(f"LLM summary formatting failed: {e}")
        from icu_copilot.ingest.schemas import SummaryBullet
        return SummaryOutput(summary=[SummaryBullet(text=b["text"], evidence_ids=b["evidence_ids"]) for b in bullets])


def compose_report_with_llm(
    summary: SummaryOutput,
    differential: DifferentialOutput,
    evidence_snips: str,
    llm: OllamaClient,
) -> dict | None:
    """
    Compose conjoined report using minimal-context LLM prompt.
    Returns dict that can be parsed into ConjoinedReport.
    """
    # Use only top 4-6 templates to keep context small
    templates_subset = QUESTION_TEMPLATES[:6]
    templates_json = json.dumps(templates_subset, indent=2)
    
    summary_json = summary.model_dump_json(indent=2)
    differential_json = differential.model_dump_json(indent=2)
    
    # Log sizes
    total_input = len(summary_json) + len(differential_json) + len(evidence_snips) + len(templates_json)
    logger.info(f"Compose report input: ~{estimate_tokens(str(total_input))} tokens")
    
    prompt = REPORT_COMPOSE_MIN_PROMPT.format(
        summary_json=summary_json,
        differential_json=differential_json,
        evidence_snips=evidence_snips,
        templates_json=templates_json,
    )
    
    logger.info(f"Compose prompt: {len(prompt)} chars (~{estimate_tokens(prompt)} tokens)")
    
    raw = llm.generate(prompt, json_mode=True)
    
    if not raw or raw.strip() in ("", "{}"):
        logger.warning("LLM returned empty response for report composition")
        return None
    
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse LLM response: {e}")
        return None


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    
    # Resolve to the repo root (same as run_all) so data/ sits beside src/
    root = Path(__file__).resolve().parents[3]
    run_dir = root / "data" / "processed" / "runs" / "latest"
    indices_dir = root / "data" / "indices"

    # Load inputs
    patient_state = PatientState.model_validate(load_json(run_dir / "patient_state.json"))
    
    # Try to load ICU summary first, fall back to legacy summary
    icu_summary_path = run_dir / "icu_summary.json"
    legacy_summary_path = run_dir / "summary.json"
    
    if icu_summary_path.exists():
        icu_summary = ICUStructuredSummary.model_validate(load_json(icu_summary_path))
    else:
        icu_summary = None
    
    legacy_summary = SummaryOutput.model_validate(load_json(legacy_summary_path))
    dx = DifferentialOutput.model_validate(load_json(run_dir / "differential.json"))

    # Initialize components
    llm = OllamaClient()
    retriever = HybridRetriever(indices_dir)
    
    # Get evidence snippets for context
    evidence_snips = build_evidence_snippets(retriever, top_k=8)
    
    # Format summary with LLM if we have ICU summary
    if icu_summary:
        formatted_summary = format_icu_summary_with_llm(icu_summary, llm)
    else:
        formatted_summary = legacy_summary
    
    # Compose report with minimal context
    composed = compose_report_with_llm(formatted_summary, dx, evidence_snips, llm)
    
    if composed:
        # Parse into structured report
        try:
            # Extract LLM-generated questions/actions
            llm_questions = [
                ClarifyingQuestion.model_validate(q) 
                for q in composed.get("clarifying_questions", [])
            ]
            llm_actions = [
                ActionItem.model_validate(a) 
                for a in composed.get("action_items", [])
            ]
            llm_limitations = composed.get("limitations", [])
            
            # If LLM didn't generate enough questions, add deterministic ones
            if len(llm_questions) < 3:
                logger.info("LLM generated few questions, adding deterministic fallback")
                # Get evidence IDs from snippets
                evidence_ids = [line.split("]")[0][1:] for line in evidence_snips.split("\n") if line.startswith("[")]
                det_questions = generate_deterministic_questions(dx, evidence_ids)
                # Add deterministic questions that don't duplicate
                existing_q_texts = {q.question.lower() for q in llm_questions}
                for dq in det_questions:
                    if dq.question.lower() not in existing_q_texts:
                        llm_questions.append(dq)
                        if len(llm_questions) >= 5:
                            break
            
            # If LLM didn't generate actions, add deterministic ones
            if len(llm_actions) < 1:
                logger.info("LLM generated no actions, adding deterministic fallback")
                llm_actions = generate_deterministic_actions(dx)
            
            # Build full report
            report = ConjoinedReport(
                patient_state=patient_state,
                summary=formatted_summary.summary,
                differential=dx.differential,
                clarifying_questions=llm_questions,
                action_items=llm_actions,
                limitations=llm_limitations,
            )
        except Exception as e:
            logger.warning(f"Failed to parse composed report: {e}")
            # Fallback to deterministic
            evidence_ids = [line.split("]")[0][1:] for line in evidence_snips.split("\n") if line.startswith("[")]
            report = ConjoinedReport(
                patient_state=patient_state,
                summary=formatted_summary.summary,
                differential=dx.differential,
                clarifying_questions=generate_deterministic_questions(dx, evidence_ids),
                action_items=generate_deterministic_actions(dx),
                limitations=["Report composition partially failed; using deterministic questions."],
            )
    else:
        # Fallback: if LLM output is invalid or empty, use deterministic generation
        logger.info("LLM composition failed, using fully deterministic fallback")
        evidence_ids = [line.split("]")[0][1:] for line in evidence_snips.split("\n") if line.startswith("[")]
        report = ConjoinedReport(
            patient_state=patient_state,
            summary=formatted_summary.summary,
            differential=dx.differential,
            clarifying_questions=generate_deterministic_questions(dx, evidence_ids),
            action_items=generate_deterministic_actions(dx),
            limitations=["LLM composition failed; using deterministic generation."],
        )

    # Save outputs
    (run_dir / "report.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")
    (run_dir / "formatted_summary.json").write_text(formatted_summary.model_dump_json(indent=2), encoding="utf-8")
    
    logger.info("Report composition complete")
    logger.info(f"Clarifying questions: {len(report.clarifying_questions)}")
    logger.info(f"Action items: {len(report.action_items)}")


if __name__ == "__main__":
    main()
