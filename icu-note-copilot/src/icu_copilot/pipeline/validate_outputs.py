from __future__ import annotations

from icu_copilot.ingest.schemas import SummaryOutput, DifferentialOutput, VerificationReport, VerificationFinding


def _exists(eid: str, store: dict) -> bool:
    return eid in store


def validate_summary(summary: SummaryOutput, store: dict) -> VerificationReport:
    findings: list[VerificationFinding] = []
    if len(summary.summary) == 0:
        findings.append(VerificationFinding(severity="error", message="Summary is empty."))

    for b in summary.summary:
        if not b.evidence_ids:
            findings.append(VerificationFinding(severity="error", message="Summary bullet missing evidence_ids.", offending_text=b.text))
            continue
        missing = [eid for eid in b.evidence_ids if not _exists(eid, store)]
        if missing:
            findings.append(VerificationFinding(severity="error", message="Summary bullet references unknown evidence_ids.", offending_text=b.text, missing_evidence_ids=missing))

    ok = all(f.severity != "error" for f in findings)
    return VerificationReport(ok=ok, findings=findings)


def validate_differential(dx_out: DifferentialOutput, store: dict) -> VerificationReport:
    findings: list[VerificationFinding] = []
    
    # Quality gate: require at least 3 differential diagnoses
    if len(dx_out.differential) < 3:
        findings.append(VerificationFinding(severity="warning", message="Differential has < 3 items."))
    
    for dx in dx_out.differential:
        # Quality gate: each diagnosis needs at least 2 support items
        if len(dx.support) < 2:
            findings.append(VerificationFinding(severity="warning", message="Diagnosis has < 2 supports.", offending_text=dx.diagnosis))
        
        # Quality gate: each diagnosis needs at least 1 missing discriminator
        if len(dx.missing) < 1:
            findings.append(VerificationFinding(severity="warning", message="Diagnosis missing discriminators absent.", offending_text=dx.diagnosis))
        
        for block_name in ["support", "against"]:
            facts = getattr(dx, block_name)
            for f in facts:
                bad = [eid for eid in f.evidence_ids if eid.startswith(("D", "C"))]
                if bad:
                    findings.append(
                        VerificationFinding(
                            severity="error",
                            message=f"Differential {block_name} uses non-patient evidence (D/C). Put these into references instead.",
                            offending_text=f"{dx.diagnosis}::{f.label}",
                            missing_evidence_ids=bad,
                        )
                    )
                missing = [eid for eid in f.evidence_ids if not _exists(eid, store)]
                if missing:
                    findings.append(
                        VerificationFinding(
                            severity="error",
                            message="Differential references unknown evidence_ids.",
                            offending_text=f"{dx.diagnosis}::{f.label}",
                            missing_evidence_ids=missing,
                        )
                    )

    ok = all(f.severity != "error" for f in findings)
    return VerificationReport(ok=ok, findings=findings)
