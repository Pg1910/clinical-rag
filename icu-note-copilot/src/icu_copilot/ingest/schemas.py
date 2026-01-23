"""Data schemas for parsed documents"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional, List

from pydantic import BaseModel, Field


EvidenceType = Literal["narrative", "lab", "monitor", "codebook", "domain"]


class EvidenceRecord(BaseModel):
    evidence_id: str
    evidence_type: EvidenceType
    source_file: str
    raw_text: str
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)


class NarrativeSpan(EvidenceRecord):
    evidence_type: Literal["narrative"] = "narrative"


class CodebookRecord(EvidenceRecord):
    evidence_type: Literal["codebook"] = "codebook"
    code: Optional[int] = None
    name: Optional[str] = None
    unit: Optional[str] = None


class DomainRecord(EvidenceRecord):
    evidence_type: Literal["domain"] = "domain"
    title: Optional[str] = None


class LabRecord(EvidenceRecord):
    evidence_type: Literal["lab"] = "lab"
    dt: datetime
    test: str
    value: float | str
    unit: Optional[str] = None


class MonitorRecord(EvidenceRecord):
    evidence_type: Literal["monitor"] = "monitor"
    t: str  # HH:MM:SS as in file
    code: int
    value: float | int | str
    name: Optional[str] = None
    unit: Optional[str] = None


class ExtractedFact(BaseModel):
    label: str
    value: str
    evidence_ids: List[str] = Field(default_factory=list)


class PatientState(BaseModel):
    demographics: List[ExtractedFact] = Field(default_factory=list)
    diagnoses: List[ExtractedFact] = Field(default_factory=list)
    procedures: List[ExtractedFact] = Field(default_factory=list)
    supports: List[ExtractedFact] = Field(default_factory=list)
    meds: List[ExtractedFact] = Field(default_factory=list)
    timeline: List[ExtractedFact] = Field(default_factory=list)


class SummaryBullet(BaseModel):
    text: str
    evidence_ids: List[str]


# --- ICU Structured Summary Sections ---
class ICUSectionBullet(BaseModel):
    """A single bullet within an ICU summary section."""
    text: str
    evidence_ids: List[str] = Field(default_factory=list)


class ICUStructuredSummary(BaseModel):
    """Clinical ICU-format structured summary with organ-system organization."""
    # Patient identification
    patient_info: List[ICUSectionBullet] = Field(
        default_factory=list,
        description="Age/sex/weight and key identifiers"
    )
    # Primary problems (top 2-3 acute issues)
    primary_problems: List[ICUSectionBullet] = Field(
        default_factory=list,
        description="Top acute problems (e.g., hepatic failure, sepsis, ARDS)"
    )
    # Organ systems
    respiratory: List[ICUSectionBullet] = Field(default_factory=list)
    cardiovascular: List[ICUSectionBullet] = Field(default_factory=list)
    hepatic: List[ICUSectionBullet] = Field(default_factory=list)
    renal: List[ICUSectionBullet] = Field(default_factory=list)
    hematology_coag: List[ICUSectionBullet] = Field(default_factory=list)
    infectious: List[ICUSectionBullet] = Field(default_factory=list)
    neurologic: List[ICUSectionBullet] = Field(default_factory=list)
    # Key labs
    key_labs: List[ICUSectionBullet] = Field(default_factory=list)
    # Supports/devices
    supports: List[ICUSectionBullet] = Field(
        default_factory=list,
        description="Ventilator, lines, drains - only if M-codes support"
    )
    # Procedures/history
    procedures: List[ICUSectionBullet] = Field(default_factory=list)


class DxHypothesis(BaseModel):
    diagnosis: str
    support: List[ExtractedFact] = Field(default_factory=list)
    against: List[ExtractedFact] = Field(default_factory=list)
    missing: List[str] = Field(default_factory=list)
    references: List[str] = Field(default_factory=list)  # evidence_ids allowed to be D/C
    confidence: Literal["low", "medium", "high"] = "low"



class FinalOutput(BaseModel):
    summary: List[SummaryBullet] = Field(default_factory=list)
    differential: List[DxHypothesis] = Field(default_factory=list)


class VerificationFinding(BaseModel):
    severity: Literal["error", "warning", "info"]
    message: str
    offending_text: Optional[str] = None
    missing_evidence_ids: List[str] = Field(default_factory=list)


class VerificationReport(BaseModel):
    ok: bool
    findings: List[VerificationFinding] = Field(default_factory=list)


class QualityGateResult(BaseModel):
    """Objective quality scoring for outputs."""
    passed: bool
    score: int = Field(ge=0, le=100, description="Quality score 0-100")
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    metrics: dict = Field(default_factory=dict)


class SummaryOutput (BaseModel):
    summary: List[SummaryBullet] = Field(default_factory=list)


class ICUSummaryOutput(BaseModel):
    """ICU-format structured summary output."""
    structured_summary: ICUStructuredSummary


class DifferentialOutput(BaseModel):
    differential: List[DxHypothesis] = Field(default_factory=list)

class ClarifyingQuestion(BaseModel):
    question: str
    rationale: str
    evidence_ids: List[str] = Field(default_factory=list)
    priority: Literal["critical","high","medium","low"] = "medium"

class ActionItem(BaseModel):
    item: str
    rationale: str
    evidence_ids: List[str] = Field(default_factory=list)
    priority: Literal["critical","high","medium","low"] = "medium"

class ConjoinedReport(BaseModel):
    patient_state: PatientState
    summary: List[SummaryBullet]
    differential: List[DxHypothesis]
    clarifying_questions: List[ClarifyingQuestion] = Field(default_factory=list)
    action_items: List[ActionItem] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
