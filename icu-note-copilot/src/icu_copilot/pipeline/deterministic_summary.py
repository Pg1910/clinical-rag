from __future__ import annotations

from icu_copilot.ingest.schemas import (
    PatientState, 
    SummaryBullet,
    ICUStructuredSummary,
    ICUSectionBullet,
)


def build_summary_candidates(ps: PatientState) -> list[SummaryBullet]:
    """Legacy flat summary builder - kept for backwards compatibility."""
    bullets: list[SummaryBullet] = []

    # Demographics
    if ps.demographics:
        for f in ps.demographics:
            bullets.append(SummaryBullet(text=f"{f.label}: {f.value}", evidence_ids=f.evidence_ids))

    # Key diagnoses (top 5)
    for f in ps.diagnoses[:5]:
        bullets.append(SummaryBullet(text=f"Problem: {f.value}", evidence_ids=f.evidence_ids))

    # Procedures/supports
    for f in ps.procedures[:3]:
        bullets.append(SummaryBullet(text=f"Procedure/history: {f.value}", evidence_ids=f.evidence_ids))

    # Medications
    for f in ps.meds[:5]:
        bullets.append(SummaryBullet(text=f"Medication: {f.value}", evidence_ids=f.evidence_ids))

    # Labs (timeline currently contains labs)
    # Keep a few high-signal ones as "latest notable labs"
    for f in ps.timeline[:6]:
        bullets.append(SummaryBullet(text=f"Lab: {f.label} = {f.value}", evidence_ids=f.evidence_ids))

    # De-duplicate exact texts while preserving first occurrence
    seen = set()
    out: list[SummaryBullet] = []
    for b in bullets:
        if b.text not in seen and b.evidence_ids:
            out.append(b)
            seen.add(b.text)

    return out[:10]


def build_icu_structured_summary(ps: PatientState) -> ICUStructuredSummary:
    """
    Build an ICU-format structured summary deterministically from PatientState.
    Organizes by organ system for clinical readability.
    """
    
    # Helper to create bullet
    def bullet(text: str, eids: list[str]) -> ICUSectionBullet:
        return ICUSectionBullet(text=text, evidence_ids=eids)
    
    # --- Patient Info ---
    patient_info = []
    for f in ps.demographics:
        if f.evidence_ids:
            patient_info.append(bullet(f"{f.label}: {f.value}", f.evidence_ids))
    
    # --- Primary Problems (top 3 diagnoses) ---
    primary_problems = []
    for f in ps.diagnoses[:3]:
        if f.evidence_ids:
            primary_problems.append(bullet(f.value, f.evidence_ids))
    
    # --- Organ Systems (classify diagnoses) ---
    respiratory, hepatic, renal, infectious, hematology_coag = [], [], [], [], []
    cardiovascular, neurologic = [], []
    
    # Keywords for classification
    RESP_KEYWORDS = {"ards", "respiratory", "lung", "ventilat", "pneumo", "hypox", "fio2", "peep"}
    HEPATIC_KEYWORDS = {"liver", "hepat", "biliary", "kasai", "cholang", "bilirubin", "ast", "alt", "portal"}
    RENAL_KEYWORDS = {"kidney", "renal", "bun", "creatinine", "oligur", "anuri", "dialysis"}
    INFECTIOUS_KEYWORDS = {"sepsis", "septic", "infect", "bacteria", "e.coli", "culture", "antibiotic"}
    COAG_KEYWORDS = {"coagul", "pt ", "ptt", "inr", "platelet", "bleed", "dic", "fibrinogen"}
    CARDIO_KEYWORDS = {"cardiac", "heart", "bp", "hypotens", "shock", "map", "vasopressor"}
    NEURO_KEYWORDS = {"neuro", "mental", "encephalop", "seizure", "gcs"}
    
    def classify_text(text: str) -> str:
        t = text.lower()
        if any(k in t for k in RESP_KEYWORDS):
            return "respiratory"
        if any(k in t for k in HEPATIC_KEYWORDS):
            return "hepatic"
        if any(k in t for k in RENAL_KEYWORDS):
            return "renal"
        if any(k in t for k in INFECTIOUS_KEYWORDS):
            return "infectious"
        if any(k in t for k in COAG_KEYWORDS):
            return "coag"
        if any(k in t for k in CARDIO_KEYWORDS):
            return "cardiovascular"
        if any(k in t for k in NEURO_KEYWORDS):
            return "neurologic"
        return "other"
    
    # Classify all diagnoses beyond top 3
    for f in ps.diagnoses[3:]:
        if not f.evidence_ids:
            continue
        cat = classify_text(f.value)
        b = bullet(f.value, f.evidence_ids)
        if cat == "respiratory":
            respiratory.append(b)
        elif cat == "hepatic":
            hepatic.append(b)
        elif cat == "renal":
            renal.append(b)
        elif cat == "infectious":
            infectious.append(b)
        elif cat == "coag":
            hematology_coag.append(b)
        elif cat == "cardiovascular":
            cardiovascular.append(b)
        elif cat == "neurologic":
            neurologic.append(b)
    
    # --- Key Labs (from timeline) ---
    key_labs = []
    PRIORITY_LABS = {"pt", "ptt", "inr", "bun", "creatinine", "lactate", "bilirubin", "ast", "alt", "wbc", "rbc", "platelets"}
    
    seen_labs = set()
    for f in ps.timeline:
        if not f.evidence_ids:
            continue
        lab_key = f.label.lower()
        # Prioritize key labs, dedupe
        if lab_key in seen_labs:
            continue
        if any(p in lab_key for p in PRIORITY_LABS):
            key_labs.append(bullet(f"{f.label}: {f.value}", f.evidence_ids))
            seen_labs.add(lab_key)
            # Also classify into organ systems
            if "pt" in lab_key or "ptt" in lab_key or "inr" in lab_key:
                hematology_coag.append(bullet(f"Coag: {f.label} {f.value}", f.evidence_ids))
            elif "bun" in lab_key or "creatinine" in lab_key:
                renal.append(bullet(f"{f.label}: {f.value}", f.evidence_ids))
    
    # Add remaining labs
    for f in ps.timeline:
        if f.label.lower() not in seen_labs and f.evidence_ids and len(key_labs) < 6:
            key_labs.append(bullet(f"{f.label}: {f.value}", f.evidence_ids))
            seen_labs.add(f.label.lower())
    
    # --- Supports (require M-codes for ventilator/monitor data) ---
    supports = []
    for f in ps.supports:
        if f.evidence_ids:
            # Check if any M-code evidence
            has_monitor = any(eid.startswith("M") for eid in f.evidence_ids)
            if has_monitor or any(eid.startswith("N") for eid in f.evidence_ids):
                supports.append(bullet(f.value, f.evidence_ids))
    
    # --- Procedures ---
    procedures = []
    for f in ps.procedures[:3]:
        if f.evidence_ids:
            procedures.append(bullet(f.value, f.evidence_ids))
    
    return ICUStructuredSummary(
        patient_info=patient_info[:2],
        primary_problems=primary_problems[:3],
        respiratory=respiratory[:3],
        cardiovascular=cardiovascular[:2],
        hepatic=hepatic[:3],
        renal=renal[:2],
        hematology_coag=hematology_coag[:3],
        infectious=infectious[:3],
        neurologic=neurologic[:2],
        key_labs=key_labs[:6],
        supports=supports[:3],
        procedures=procedures[:3],
    )
