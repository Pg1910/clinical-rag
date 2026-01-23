"""Evidence validation rules for clinical safety"""
from __future__ import annotations

from icu_copilot.ingest.schemas import PatientState, FinalOutput, VerificationReport, VerificationFinding


def _bad_ids(evidence_ids: list[str], forbidden_prefixes: tuple[str, ...]) -> list[str]:
    return [eid for eid in evidence_ids if eid[:1] in forbidden_prefixes]


def validate_patient_state_evidence(ps: PatientState) -> VerificationReport:
    findings: list[VerificationFinding] = []

    def check_fact(group: str, label: str, eids: list[str]) -> None:
        bad = _bad_ids(eids, ("D", "C"))  # forbid domain/codebook for patient facts
        if bad:
            findings.append(
                VerificationFinding(
                    severity="error",
                    message=f"{group}:{label} uses non-patient evidence ids (domain/codebook): {bad}",
                    offending_text=label,
                    missing_evidence_ids=bad,
                )
            )

    for group_name in ["demographics", "diagnoses", "procedures", "supports", "meds", "timeline"]:
        group = getattr(ps, group_name)
        for fact in group:
            if not fact.evidence_ids:
                findings.append(
                    VerificationFinding(
                        severity="error",
                        message=f"{group_name}:{fact.label} missing evidence_ids",
                        offending_text=fact.label,
                        missing_evidence_ids=[],
                    )
                )
            check_fact(group_name, fact.label, fact.evidence_ids)

    return VerificationReport(ok=(len([f for f in findings if f.severity == "error"]) == 0), findings=findings)
