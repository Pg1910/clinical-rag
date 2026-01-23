from __future__ import annotations

import json
import logging
from pathlib import Path

from icu_copilot.logging_conf import setup_logging
from icu_copilot.config import SETTINGS
from icu_copilot.llm.client import OllamaClient, truncate_evidence_list, estimate_tokens
from icu_copilot.llm.prompts import (
    EXTRACTION_PROMPT,
    SUMMARY_POLISH_PROMPT,
    DIFFERENTIAL_PROMPT,
    ICU_SUMMARY_PROMPT,
    VERIFIER_PROMPT,
)
from icu_copilot.llm.json_guard import parse_with_schema
from icu_copilot.ingest.schemas import (
    PatientState,
    FinalOutput,
    SummaryOutput,
    DifferentialOutput,
    VerificationReport,
    ExtractedFact,
    ICUSummaryOutput,
    ICUStructuredSummary,
)
from icu_copilot.pipeline.deterministic_summary import build_summary_candidates, build_icu_structured_summary
from icu_copilot.pipeline.validate_outputs import validate_summary, validate_differential
from icu_copilot.pipeline.quality_gate import evaluate_summary_quality, evaluate_differential_quality, evaluate_combined_quality
from icu_copilot.pipeline.differential_cleanup import run_all_cleanups
from icu_copilot.rag.retrieve import HybridRetriever
from icu_copilot.pipeline.evidence_rules import validate_patient_state_evidence


def main() -> None:
    setup_logging(logging.INFO)
    root = Path(__file__).resolve().parents[3]
    indices_dir = root / "data" / "indices"
    processed_dir = root / "data" / "processed"
    runs_dir = processed_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    retriever = HybridRetriever(indices_dir)
    llm = OllamaClient()

    # ---------- Extraction ----------
    # Retrieve narrative evidence (N) and lab/monitor evidence (L/M) only
    # REDUCED counts to stay within context limits
    n_evs = [e for e in retriever.hybrid_search("biliary atresia Kasai sepsis ARDS liver failure coagulopathy meds", top_k=20)
             if e.evidence_id.startswith("N")][:10]  # Reduced from 18 to 10

    lm_evs = [e for e in retriever.hybrid_search("PT PTT BUN RBC FiO2 PEEP PIP MAP tidal volume respiratory rate", top_k=20)
              if (e.evidence_id.startswith("L") or e.evidence_id.startswith("M"))][:8]  # Reduced from 18 to 8

    # Use smart truncation for evidence text
    all_evs = [{"evidence_id": e.evidence_id, "text": e.text} for e in (n_evs + lm_evs)]
    ev_text = truncate_evidence_list(all_evs, max_total_chars=SETTINGS.max_evidence_chars)
    
    logging.info(f"Extraction: {len(all_evs)} evidence items, {len(ev_text)} chars (~{estimate_tokens(ev_text)} tokens)")

    ext_prompt = EXTRACTION_PROMPT.format(evidence=ev_text)
    ext_raw = llm.generate(ext_prompt, json_mode=True)
    patient_state = parse_with_schema(ext_raw, PatientState)

    # ---------- Validate Evidence Rules ----------
    ps_check = validate_patient_state_evidence(patient_state)
    if not ps_check.ok:
        run_dir = runs_dir / "latest"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "patient_state_evidence_errors.json").write_text(ps_check.model_dump_json(indent=2))
        raise RuntimeError("PatientState evidence rules violated. See patient_state_evidence_errors.json")

    # ---------- ICU Structured Summary (NEW FORMAT) ----------
    # Build deterministic ICU structured summary
    icu_summary = build_icu_structured_summary(patient_state)
    
    # Optional: enhance with LLM if context budget allows
    ps_json_for_summary = patient_state.model_dump_json(indent=2)
    if estimate_tokens(ps_json_for_summary) < 2000:
        # Retrieve additional evidence for summary enrichment
        summary_evs = [{"evidence_id": e.evidence_id, "text": e.text} 
                       for e in (n_evs + lm_evs)[:12]]
        summary_ev_text = truncate_evidence_list(summary_evs, max_total_chars=3000)
        
        icu_prompt = ICU_SUMMARY_PROMPT.format(
            patient_state=ps_json_for_summary,
            evidence=summary_ev_text,
        )
        logging.info(f"ICU Summary prompt: {len(icu_prompt)} chars (~{estimate_tokens(icu_prompt)} tokens)")
        
        try:
            icu_raw = llm.generate(icu_prompt, json_mode=True)
            icu_summary_out = parse_with_schema(icu_raw, ICUSummaryOutput)
            icu_summary = icu_summary_out.structured_summary
            logging.info("LLM-enhanced ICU summary generated")
        except Exception as e:
            logging.warning(f"LLM ICU summary failed, using deterministic: {e}")
    
    # Also keep legacy flat summary for backwards compatibility
    legacy_summary = SummaryOutput(summary=build_summary_candidates(patient_state))

    # ---------- Differential ----------
    # Use fewer evidence items for differential to stay within context
    dx_evidence = retriever.hybrid_search("ARDS sepsis coagulopathy liver failure", top_k=6)  # Reduced from 10
    dx_evs = [{"evidence_id": e.evidence_id, "text": e.text} for e in dx_evidence]
    dx_text = truncate_evidence_list(dx_evs, max_total_chars=4000)  # Smaller budget for differential
    
    # Also truncate patient state if needed
    ps_json = patient_state.model_dump_json(indent=2)
    if len(ps_json) > 3000:
        # Simplify patient state for differential prompt
        ps_simplified = {
            "diagnoses": [d.model_dump() for d in patient_state.diagnoses[:5]],
            "supports": [s.model_dump() for s in patient_state.supports[:3]],
            "timeline": [t.model_dump() for t in patient_state.timeline[:4]],
        }
        ps_json = json.dumps(ps_simplified, indent=2)
        logging.info(f"Simplified patient state for differential: {len(ps_json)} chars")

    dx_prompt = DIFFERENTIAL_PROMPT.format(
        patient_state=ps_json,
        evidence=dx_text,
    )
    logging.info(f"Differential prompt: {len(dx_prompt)} chars (~{estimate_tokens(dx_prompt)} tokens)")
    
    dx_raw = llm.generate(dx_prompt, json_mode=True)
    dx_out = parse_with_schema(dx_raw, DifferentialOutput)

    # ---------- Deterministic Differential Cleanup ----------
    # Apply post-processing rules:
    # - Fix Kasai evidence ID (should be N000002)
    # - Remove weak supports (e.g., RBC for AKI)
    # - Enforce minimum supports (downgrade confidence if < 2)
    dx_out = run_all_cleanups(dx_out)

    # ---------- Populate empty 'against' deterministically ----------
    for dx in dx_out.differential:
        if not dx.against:
            dx.against.append(
                ExtractedFact(
                    label="No documented contradictory evidence",
                    value="No explicit negating findings in available records",
                    evidence_ids=[]
                )
            )

    # ---------- Combine Outputs ----------
    final_out = FinalOutput(
        summary=legacy_summary.summary,
        differential=dx_out.differential,
    )
    
    # ---------- Verification ----------
    sum_report = validate_summary(legacy_summary, retriever.store)
    dx_report = validate_differential(dx_out, retriever.store)
    
    # ---------- Quality Gate (NEW) ----------
    summary_quality = evaluate_summary_quality(icu_summary)
    differential_quality = evaluate_differential_quality(dx_out)
    combined_quality = evaluate_combined_quality(icu_summary, dx_out)

    # ---------- Persist ----------
    run_dir = runs_dir / "latest"
    run_dir.mkdir(parents=True, exist_ok=True)

    (run_dir / "patient_state.json").write_text(patient_state.model_dump_json(indent=2))
    (run_dir / "summary.json").write_text(legacy_summary.model_dump_json(indent=2))
    (run_dir / "icu_summary.json").write_text(icu_summary.model_dump_json(indent=2))
    (run_dir / "differential.json").write_text(dx_out.model_dump_json(indent=2))
    (run_dir / "final_output.json").write_text(final_out.model_dump_json(indent=2))
    (run_dir / "verification_summary.json").write_text(sum_report.model_dump_json(indent=2))
    (run_dir / "verification_differential.json").write_text(dx_report.model_dump_json(indent=2))
    (run_dir / "quality_gate.json").write_text(combined_quality.model_dump_json(indent=2))

    if not (sum_report.ok and dx_report.ok):
        raise RuntimeError("Deterministic verification failed. See verification_*.json.")

    logging.info("=" * 50)
    logging.info("LLM PIPELINE COMPLETED")
    logging.info("=" * 50)
    logging.info(f"Summary verification OK: {sum_report.ok}")
    logging.info(f"Differential verification OK: {dx_report.ok}")
    logging.info("-" * 50)
    logging.info("QUALITY GATE RESULTS:")
    logging.info(f"  Summary Score: {summary_quality.score}/100 ({'PASS' if summary_quality.passed else 'FAIL'})")
    logging.info(f"  Differential Score: {differential_quality.score}/100 ({'PASS' if differential_quality.passed else 'FAIL'})")
    logging.info(f"  Combined Score: {combined_quality.score}/100 ({'PASS' if combined_quality.passed else 'FAIL'})")
    if combined_quality.warnings:
        logging.warning(f"  Warnings: {len(combined_quality.warnings)}")
        for w in combined_quality.warnings[:5]:
            logging.warning(f"    - {w}")
    if combined_quality.errors:
        logging.error(f"  Errors: {len(combined_quality.errors)}")
        for e in combined_quality.errors[:5]:
            logging.error(f"    - {e}")
    logging.info("=" * 50)


if __name__ == "__main__":
    main()
