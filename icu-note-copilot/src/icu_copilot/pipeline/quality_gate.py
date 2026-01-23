"""Quality gate for objective scoring of ICU outputs."""
from __future__ import annotations

from icu_copilot.ingest.schemas import (
    QualityGateResult,
    ICUStructuredSummary,
    ICUSummaryOutput,
    SummaryOutput,
    DifferentialOutput,
)


def count_icu_summary_bullets(summary: ICUStructuredSummary) -> int:
    """Count total bullets across all sections."""
    total = 0
    total += len(summary.patient_info)
    total += len(summary.primary_problems)
    total += len(summary.respiratory)
    total += len(summary.cardiovascular)
    total += len(summary.hepatic)
    total += len(summary.renal)
    total += len(summary.hematology_coag)
    total += len(summary.infectious)
    total += len(summary.neurologic)
    total += len(summary.key_labs)
    total += len(summary.supports)
    total += len(summary.procedures)
    return total


def evaluate_summary_quality(summary: ICUStructuredSummary) -> QualityGateResult:
    """
    Evaluate ICU structured summary quality.
    
    Criteria:
    - At least 6 total bullets
    - At least 1 primary problem
    - At least 2 key labs
    - Each bullet must have evidence_ids
    """
    warnings = []
    errors = []
    
    total_bullets = count_icu_summary_bullets(summary)
    
    # Metrics
    metrics = {
        "total_bullets": total_bullets,
        "primary_problems": len(summary.primary_problems),
        "key_labs": len(summary.key_labs),
        "organ_systems_covered": sum([
            1 if summary.respiratory else 0,
            1 if summary.cardiovascular else 0,
            1 if summary.hepatic else 0,
            1 if summary.renal else 0,
            1 if summary.hematology_coag else 0,
            1 if summary.infectious else 0,
            1 if summary.neurologic else 0,
        ]),
    }
    
    # Check criteria
    if total_bullets < 6:
        warnings.append(f"Summary has only {total_bullets} bullets (min: 6)")
    
    if len(summary.primary_problems) < 1:
        errors.append("No primary problems identified")
    
    if len(summary.key_labs) < 2:
        warnings.append(f"Only {len(summary.key_labs)} key labs (recommend: 2+)")
    
    # Check for missing evidence_ids
    all_bullets = (
        summary.patient_info + summary.primary_problems + 
        summary.respiratory + summary.cardiovascular +
        summary.hepatic + summary.renal + summary.hematology_coag +
        summary.infectious + summary.neurologic +
        summary.key_labs + summary.supports + summary.procedures
    )
    
    missing_evidence = sum(1 for b in all_bullets if not b.evidence_ids)
    if missing_evidence > 0:
        errors.append(f"{missing_evidence} bullets missing evidence_ids")
    
    # Calculate score (0-100)
    score = 100
    score -= len(errors) * 20
    score -= len(warnings) * 10
    score = max(0, min(100, score))
    
    passed = len(errors) == 0 and score >= 60
    
    return QualityGateResult(
        passed=passed,
        score=score,
        warnings=warnings,
        errors=errors,
        metrics=metrics,
    )


def evaluate_differential_quality(dx_out: DifferentialOutput) -> QualityGateResult:
    """
    Evaluate differential diagnosis quality.
    
    Criteria:
    - At least 3 differential diagnoses
    - Each dx has at least 2 support items
    - Each dx has at least 1 missing discriminator
    - Diagnoses are distinct (no overlapping mechanisms)
    """
    warnings = []
    errors = []
    
    dx_count = len(dx_out.differential)
    
    # Metrics
    metrics = {
        "differential_count": dx_count,
        "avg_supports": 0,
        "avg_missing": 0,
        "diagnoses": [],
    }
    
    if dx_count == 0:
        errors.append("No differential diagnoses generated")
        return QualityGateResult(
            passed=False, score=0, warnings=warnings, errors=errors, metrics=metrics
        )
    
    # Check count
    if dx_count < 3:
        warnings.append(f"Differential has only {dx_count} items (min: 3)")
    
    total_supports = 0
    total_missing = 0
    dx_names = []
    
    for dx in dx_out.differential:
        dx_names.append(dx.diagnosis)
        metrics["diagnoses"].append(dx.diagnosis)
        
        # Check support count
        support_count = len(dx.support)
        total_supports += support_count
        if support_count < 2:
            warnings.append(f"'{dx.diagnosis}' has only {support_count} support items (min: 2)")
        
        # Check missing discriminators
        missing_count = len(dx.missing)
        total_missing += missing_count
        if missing_count < 1:
            warnings.append(f"'{dx.diagnosis}' has no missing discriminators")
        
        # Check for evidence in support
        for s in dx.support:
            if not s.evidence_ids:
                errors.append(f"'{dx.diagnosis}' support '{s.label}' has no evidence_ids")
    
    metrics["avg_supports"] = round(total_supports / dx_count, 1)
    metrics["avg_missing"] = round(total_missing / dx_count, 1)
    
    # Check for overlapping diagnoses (simple heuristic)
    OVERLAP_PATTERNS = [
        ({"hepatic", "liver"}, "hepatic failure"),
        ({"sepsis", "septic"}, "sepsis"),
        ({"ards", "respiratory"}, "respiratory failure"),
    ]
    
    for pattern_set, pattern_name in OVERLAP_PATTERNS:
        matches = [dx for dx in dx_names if any(p in dx.lower() for p in pattern_set)]
        if len(matches) > 1:
            warnings.append(f"Possible overlapping {pattern_name} diagnoses: {matches}")
    
    # Calculate score
    score = 100
    score -= len(errors) * 25
    score -= len(warnings) * 8
    
    # Bonus for meeting targets
    if dx_count >= 3:
        score += 5
    if metrics["avg_supports"] >= 2:
        score += 5
    if metrics["avg_missing"] >= 1:
        score += 5
    
    score = max(0, min(100, score))
    
    passed = len(errors) == 0 and score >= 60
    
    return QualityGateResult(
        passed=passed,
        score=score,
        warnings=warnings,
        errors=errors,
        metrics=metrics,
    )


def evaluate_combined_quality(
    summary: ICUStructuredSummary,
    differential: DifferentialOutput,
) -> QualityGateResult:
    """Combined quality gate for both summary and differential."""
    
    sum_result = evaluate_summary_quality(summary)
    dx_result = evaluate_differential_quality(differential)
    
    # Combine results
    combined_warnings = [f"[Summary] {w}" for w in sum_result.warnings]
    combined_warnings += [f"[Differential] {w}" for w in dx_result.warnings]
    
    combined_errors = [f"[Summary] {e}" for e in sum_result.errors]
    combined_errors += [f"[Differential] {e}" for e in dx_result.errors]
    
    combined_metrics = {
        "summary": sum_result.metrics,
        "differential": dx_result.metrics,
        "summary_score": sum_result.score,
        "differential_score": dx_result.score,
    }
    
    # Overall score is weighted average
    combined_score = int(0.4 * sum_result.score + 0.6 * dx_result.score)
    
    passed = sum_result.passed and dx_result.passed
    
    return QualityGateResult(
        passed=passed,
        score=combined_score,
        warnings=combined_warnings,
        errors=combined_errors,
        metrics=combined_metrics,
    )
