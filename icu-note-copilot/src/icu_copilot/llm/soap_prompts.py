"""
SOAP-Structured Prompts for Clinical Summarization

Prompts designed for SOAP (Subjective, Objective, Assessment, Plan) format
with strict evidence grounding and no hallucination.
"""
from __future__ import annotations


# =============================================================================
# GLOBAL SOAP EXTRACTION PROMPT
# =============================================================================

SOAP_EXTRACTION_PROMPT = """
You are a clinical information extraction system.

TASK:
Extract structured SOAP facts from the provided EVIDENCE into a JSON structure.

SOAP SECTIONS:
- S (Subjective): Patient's symptoms, complaints, history of present illness, duration, onset
- O (Objective): Measurements, lab values, vital signs, physical exam findings
- A (Assessment): Diagnoses, impressions, problem list, differential diagnoses
- P (Plan): Treatment plans, recommendations, follow-up, orders (leave empty if not documented)

RULES (CRITICAL):
1. Every extracted fact MUST include at least one evidence_id.
2. Do NOT infer or guess. If evidence is missing, omit the fact.
3. Use ONLY patient-specific evidence (CS_, CN_, CF_, CV_, N_, L_, M_ prefixes).
4. Do NOT cite domain/background docs (D_, C_) as patient facts.
5. Output STRICT JSON ONLY. No commentary.

OUTPUT SCHEMA:
{{
  "S": [{{"label": "chief_complaint", "value": "...", "evidence_ids": ["CV_12_0"]}}],
  "O": [{{"label": "...", "value": "...", "evidence_ids": ["CS_12_4", "L_001"]}}],
  "A": [{{"label": "...", "value": "...", "evidence_ids": ["CS_12_7"]}}],
  "P": [{{"label": "...", "value": "...", "evidence_ids": ["CS_12_9"]}}]
}}

EVIDENCE:
{evidence}
"""


# =============================================================================
# SOAP SUMMARY GENERATION PROMPT
# =============================================================================

SOAP_SUMMARY_PROMPT = """
You are generating a structured clinical summary in SOAP format.

PATIENT CONTEXT:
{soap_context}

ADDITIONAL EVIDENCE:
{evidence}

TASK:
Generate a concise SOAP summary. Each bullet must cite evidence IDs in brackets.

RULES:
1. Every statement MUST cite at least one evidence_id [like this].
2. Use ONLY facts from the provided evidence.
3. If information is missing, state "Not documented" rather than guessing.
4. Be concise but clinically complete.

OUTPUT FORMAT (Markdown):

## SUBJECTIVE
- [Chief complaint and history items with citations]

## OBJECTIVE
- [Exam findings, vitals, labs with citations]

## ASSESSMENT
- [Diagnoses and clinical impressions with citations]

## PLAN
- [Treatment plan or "Information needed: [list]" if unclear]

Generate the summary:
"""


# =============================================================================
# SOAP Q&A PROMPT (SECTION-SPECIFIC)
# =============================================================================

SOAP_QA_PROMPT = """
You are answering a clinical question using SOAP-structured evidence.

SOAP CONTEXT:
{soap_context}

SECTION EVIDENCE ({section}):
{evidence}

QUESTION: {question}

RULES:
1. Answer ONLY based on the provided evidence.
2. Cite evidence IDs in brackets [CV_12_0] when making claims.
3. If evidence does not contain the answer, say "Not documented in available records."
4. Be concise but thorough.
5. Do NOT fabricate or infer data not in the evidence.

Answer:
"""


# =============================================================================
# DIFFERENTIAL DIAGNOSIS WITH SOAP CONTEXT
# =============================================================================

SOAP_DIFFERENTIAL_PROMPT = """
You are a clinical reasoning assistant.

PATIENT SOAP CONTEXT:
{soap_context}

SUPPORTING EVIDENCE:
{evidence}

TASK:
Generate a differential diagnosis list with distinct clinical entities.

RULES (CRITICAL):
1. Each diagnosis MUST have at least 2 supporting evidence items with patient evidence IDs.
2. Support/against: ONLY patient evidence (CS_, CN_, CF_, CV_, N_, L_, M_).
3. Do NOT cite domain docs (D_, C_) as patient evidence.
4. Include "missing" items: tests/data needed to confirm or rule out.
5. Assign confidence: high (>70%), moderate (40-70%), low (<40%).

OUTPUT SCHEMA:
{{
  "differential": [
    {{
      "diagnosis": "...",
      "confidence": "high|moderate|low",
      "support": [
        {{"label": "...", "value": "...", "evidence_ids": ["CS_12_5"]}}
      ],
      "against": [
        {{"label": "...", "value": "...", "evidence_ids": []}}
      ],
      "missing": ["test or data needed to discriminate"]
    }}
  ]
}}

Generate the differential:
"""


# =============================================================================
# CLARIFYING QUESTIONS GENERATION
# =============================================================================

CLARIFYING_QUESTIONS_PROMPT = """
Based on the clinical context, generate clarifying questions to fill information gaps.

SOAP CONTEXT:
{soap_context}

MISSING INFORMATION DETECTED:
{missing_slots}

TASK:
Generate 3-5 focused clinical questions that would help complete the assessment.

RULES:
1. Questions should be specific and clinically actionable.
2. Prioritize questions that would change management.
3. Format as a numbered list.

Questions:
"""


# =============================================================================
# REPORT COMPOSITION PROMPT
# =============================================================================

SOAP_REPORT_PROMPT = """
You are composing a final clinical report from structured components.

PATIENT SOAP SUMMARY:
{soap_summary}

DIFFERENTIAL DIAGNOSES:
{differential}

CLARIFYING QUESTIONS:
{questions}

TASK:
Compose a cohesive clinical report that integrates all components.

OUTPUT FORMAT:
1. Patient Summary (SOAP format with evidence citations)
2. Problem List with supporting evidence
3. Differential Diagnosis ranked by likelihood
4. Information Gaps and recommended actions
5. Immediate action items (if any)

RULES:
1. Maintain all evidence citations.
2. Do not add information not present in the inputs.
3. Highlight critical findings or urgent issues.

Report:
"""


# =============================================================================
# SLOT TEMPLATES (DETERMINISTIC)
# =============================================================================

SOAP_SLOT_TEMPLATES = {
    "S": {
        "chief_complaint": "What is the primary reason for the visit/admission?",
        "duration": "How long have symptoms been present?",
        "onset": "When did symptoms start?",
        "severity": "How severe are the symptoms (1-10 or descriptive)?",
        "associated_symptoms": "What other symptoms are present?",
        "past_medical_history": "Relevant past medical history?",
        "medications": "Current medications?",
        "allergies": "Known allergies?",
    },
    "O": {
        "vitals": "What are the vital signs (BP, HR, RR, Temp, SpO2)?",
        "general_appearance": "General appearance and mental status?",
        "physical_exam": "Key physical exam findings?",
        "labs": "Relevant laboratory values?",
        "imaging": "Any imaging results?",
    },
    "A": {
        "primary_diagnosis": "What is the primary diagnosis or impression?",
        "problem_list": "What are the active problems?",
        "differential": "What is the differential diagnosis?",
        "severity_assessment": "How severe is the condition?",
    },
    "P": {
        "treatment": "What treatment is being initiated?",
        "medications": "What medications are being prescribed?",
        "follow_up": "What follow-up is recommended?",
        "patient_education": "What patient education was provided?",
        "disposition": "What is the disposition (admit, discharge, etc.)?",
    },
}


def get_missing_slots(soap_context: dict) -> dict[str, list[str]]:
    """
    Identify missing slots in SOAP context.
    Returns dict of section -> list of missing slot labels.
    """
    missing = {}
    
    for section, templates in SOAP_SLOT_TEMPLATES.items():
        section_facts = soap_context.get(section, [])
        filled_labels = {f.get("label", "").lower() for f in section_facts}
        
        section_missing = []
        for slot_label in templates.keys():
            if slot_label.lower() not in filled_labels:
                section_missing.append(slot_label)
        
        if section_missing:
            missing[section] = section_missing
    
    return missing
