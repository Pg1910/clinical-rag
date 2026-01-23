"""Prompt templates for LLM"""
from __future__ import annotations


EXTRACTION_PROMPT = """
You are a clinical information extraction system.

TASK:
Extract structured facts ONLY from the provided EVIDENCE.

RULES (CRITICAL):
- Every extracted fact MUST include at least one evidence_id.
- Do NOT infer. Do NOT guess.
- If evidence is missing, omit the field.
- Output STRICT JSON ONLY. No commentary.

OUTPUT SCHEMA:
{{
  "demographics": [{{"label": "...", "value": "...", "evidence_ids": ["N000001"]}}],
  "diagnoses": [{{"label": "...", "value": "...", "evidence_ids": ["N000001"]}}],
  "procedures": [{{"label": "...", "value": "...", "evidence_ids": ["N000001"]}}],
  "supports": [{{"label": "...", "value": "...", "evidence_ids": ["N000001"]}}],
  "meds": [{{"label": "...", "value": "...", "evidence_ids": ["N000001"]}}],
  "timeline": [{{"label": "...", "value": "...", "evidence_ids": ["N000001"]}}]
}}

EVIDENCE:
{evidence}
"""


SUMMARY_PROMPT = """
You are a clinical summarization system.

TASK:
Produce a concise ICU patient summary.

RULES (CRITICAL):
- Every bullet MUST list evidence_ids.
- Use ONLY facts supported by evidence below.
- If you cannot support a bullet, do not write it.
- Do NOT use background domain knowledge as patient facts.

OUTPUT JSON:
{{
  "summary": [
    {{"text": "...", "evidence_ids": ["N000001","L000001"]}}
  ]
}}

PATIENT STRUCTURED FACTS:
{patient_state}

EVIDENCE (patient-specific and codebook/background may be included):
{evidence}
"""


SUMMARY_POLISH_PROMPT = """
You are rewriting ICU summary bullets for clarity.

RULES:
- Do NOT add or remove bullets.
- Do NOT change meaning.
- Keep evidence_ids exactly as provided.
- Output STRICT JSON only.

INPUT JSON:
{input_json}

OUTPUT JSON (same schema):
{{
  "summary": [
    {{"text": "...", "evidence_ids": ["N000001"]}}
  ]
}}
"""


# --- NEW ICU STRUCTURED SUMMARY PROMPT ---
ICU_SUMMARY_PROMPT = """
You are an ICU clinical documentation assistant.

TASK:
Generate a STRUCTURED ICU SUMMARY organized by organ systems.

RULES (CRITICAL):
- Every bullet MUST cite at least one evidence_id in brackets.
- Use ONLY facts directly supported by the evidence.
- If a section has no evidence, leave it as an empty array [].
- Supports/ventilator data require M-codes (monitor data) as evidence.
- Do NOT infer or fabricate data.
- Output STRICT JSON only.

OUTPUT SCHEMA:
{{
  "structured_summary": {{
    "patient_info": [{{"text": "4-month-old female, 5.2kg [N000001]", "evidence_ids": ["N000001"]}}],
    "primary_problems": [
      {{"text": "Hepatic failure secondary to biliary atresia", "evidence_ids": ["N000001", "N000006"]}}
    ],
    "respiratory": [{{"text": "ARDS on mechanical ventilation, FiO2 0.6", "evidence_ids": ["N000007", "M000001"]}}],
    "cardiovascular": [],
    "hepatic": [{{"text": "Post-Kasai, liver failure with coagulopathy", "evidence_ids": ["N000001", "N000006"]}}],
    "renal": [{{"text": "Elevated BUN 73, possible hepatorenal", "evidence_ids": ["L000040"]}}],
    "hematology_coag": [{{"text": "Coagulopathy: PT 21.8, PTT 76.6", "evidence_ids": ["L000049", "L000059"]}}],
    "infectious": [{{"text": "E. coli sepsis, ascending cholangitis", "evidence_ids": ["N000004", "N000002"]}}],
    "neurologic": [],
    "key_labs": [
      {{"text": "PT 21.8 / PTT 76.6", "evidence_ids": ["L000049", "L000059"]}},
      {{"text": "BUN 73", "evidence_ids": ["L000040"]}}
    ],
    "supports": [{{"text": "Mechanical ventilation", "evidence_ids": ["M000001"]}}],
    "procedures": [{{"text": "Kasai procedure (prior)", "evidence_ids": ["N000001"]}}]
  }}
}}

PATIENT STATE:
{patient_state}

EVIDENCE:
{evidence}
"""


DIFFERENTIAL_PROMPT = """
You are a clinical reasoning assistant.

TASK:
Generate a DIFFERENTIAL DIAGNOSIS list with DISTINCT failure mechanisms.

RULES (CRITICAL):
1. DISTINCT MECHANISMS ONLY - Diagnoses must NOT be rewordings of the same condition.
   Required distinct categories (include if evidence supports):
   - Primary hepatic failure (liver-specific pathology)
   - Primary sepsis physiology (systemic infection/inflammation)
   - Primary respiratory failure (ARDS, ventilator issues)
   - Coagulopathy differential (DIC vs hepatic coagulopathy) if PT/PTT abnormal
   - Renal dysfunction (AKI, hepatorenal) if BUN/Cr elevated

2. Each diagnosis MUST have:
   - At least 2 support items with N/L/M evidence_ids
   - At least 1 "missing" item (test/trend to discriminate)

3. Evidence rules:
   - Support/against: ONLY patient evidence (N.../L.../M...)
   - References: May include domain/codebook (D.../C...)

4. Missing items should be clinically actionable:
   - "Fibrinogen level and D-dimer to differentiate DIC vs hepatic coagulopathy"
   - "Serial lactate trend over 6h"
   - "Repeat blood cultures at 48h"

5. Confidence: low (1 support), medium (2 supports), high (3+ supports with labs)

OUTPUT JSON:
{{
  "differential": [
    {{
      "diagnosis": "Primary Hepatic Failure",
      "support": [{{"label": "...", "value": "...", "evidence_ids": ["N000001"]}}],
      "against": [],
      "missing": ["AST/ALT/bilirubin trend 48-72h", "Ammonia level"],
      "references": [],
      "confidence": "medium"
    }},
    {{
      "diagnosis": "Sepsis with Multi-organ Dysfunction",
      "support": [{{"label": "...", "value": "...", "evidence_ids": ["N000004"]}}],
      "against": [],
      "missing": ["Blood culture speciation", "Procalcitonin trend"],
      "references": [],
      "confidence": "medium"
    }},
    {{
      "diagnosis": "ARDS / Respiratory Failure",
      "support": [{{"label": "...", "value": "...", "evidence_ids": ["N000007"]}}],
      "against": [],
      "missing": ["P/F ratio calculation", "PEEP/FiO2 response"],
      "references": [],
      "confidence": "low"
    }}
  ]
}}

PATIENT STRUCTURED FACTS:
{patient_state}

PATIENT EVIDENCE:
{evidence}
"""


REPORT_COMPOSER_PROMPT = """
You are a clinical decision-support report composer.

TASK:
Produce one JSON object combining the provided components.

RULES (short):
- Do NOT invent new facts.
- Do NOT change evidence_ids.
- If you cannot propose clarifying questions or action_items, return empty lists.
- Output strict JSON per the schema below. No extra text.

SCHEMA:
{{
  "patient_state": <same as input>,
  "summary": <same as input>,
  "differential": <same as input>,
  "clarifying_questions": [
    {{"question": "...", "rationale": "...", "evidence_ids": ["N..."], "priority": "high"}}
  ],
  "action_items": [
    {{"item": "...", "rationale": "...", "evidence_ids": ["L..."], "priority": "medium"}}
  ],
  "limitations": ["..."]
}}

INPUT COMPONENTS:
PATIENT_STATE_JSON:
{patient_state_json}

SUMMARY_JSON:
{summary_json}

DIFFERENTIAL_JSON:
{differential_json}
"""


VERIFIER_PROMPT = """
You are a clinical safety verifier.

TASK:
Check the output for any unsupported claims.

RULES:
- Flag any statement without evidence_ids.
- Flag incorrect or reused evidence_ids.
- Do NOT rewrite content.

OUTPUT JSON:
{{
  "ok": true|false,
  "findings": [
    {{
      "severity": "error|warning|info",
      "message": "...",
      "offending_text": "...",
      "missing_evidence_ids": []
    }}
  ]
}}

OUTPUT TO VERIFY:
{output}
"""


# --- ICU SUMMARY TEMPLATE PROMPT (Professional Formatting) ---
ICU_SUMMARY_TEMPLATE_PROMPT = """
You are formatting an ICU summary into a professional clinical format.

RULES:
- Use ONLY facts present in INPUT.
- Do NOT add new facts.
- Keep evidence_ids exactly as provided.
- Output JSON only.

OUTPUT JSON:
{{
  "summary": [
    {{"text": "Patient: ...", "evidence_ids": ["N..."]}},
    {{"text": "Primary problems: ...", "evidence_ids": ["N..."]}},
    {{"text": "Hepatic: ...", "evidence_ids": ["N...","L..."]}},
    {{"text": "Infectious: ...", "evidence_ids": ["N..."]}},
    {{"text": "Respiratory: ...", "evidence_ids": ["N...","M..."]}},
    {{"text": "Coagulation: ...", "evidence_ids": ["L..."]}},
    {{"text": "Renal: ...", "evidence_ids": ["L..."]}}
  ]
}}

INPUT (bullets with evidence):
{input_summary_json}
"""


# --- MINIMAL REPORT COMPOSER PROMPT (Small Context) ---
REPORT_COMPOSE_MIN_PROMPT = """
You are composing a clinical decision-support report JSON.

TASK:
1. Copy summary and differential exactly as provided.
2. Generate 3-5 clarifying_questions using QUESTION_TEMPLATES as inspiration.
3. Generate 1-3 action_items for clinical workflow.
4. List any limitations.

RULES:
- Do NOT add new patient facts.
- Do NOT modify evidence_ids in summary or differential.
- Each clarifying_question MUST cite N/L/M evidence_ids from the evidence snippets.
- Questions should help discriminate between differential diagnoses.
- No treatment recommendations in questions.
- Output JSON only.

OUTPUT JSON (generate at least 3 questions):
{{
  "summary": <copy exactly from input>,
  "differential": <copy exactly from input>,
  "clarifying_questions": [
    {{"question": "What are the blood culture results and organism sensitivities?", "rationale": "Needed to confirm sepsis source and guide treatment", "evidence_ids": ["N000004"], "priority": "high"}},
    {{"question": "What is the fibrinogen level and D-dimer?", "rationale": "To differentiate DIC from hepatic coagulopathy", "evidence_ids": ["L000059"], "priority": "high"}},
    {{"question": "What is the trend of liver enzymes (AST/ALT) over 48-72h?", "rationale": "To assess hepatic failure trajectory", "evidence_ids": ["N000006"], "priority": "medium"}}
  ],
  "action_items": [
    {{"item": "Review coagulation panel trend", "rationale": "PT/PTT elevated, need to track", "evidence_ids": ["L000059", "L000049"], "priority": "high"}}
  ],
  "limitations": ["Limited monitor data available", "No medication list extracted"]
}}

INPUT SUMMARY JSON:
{summary_json}

INPUT DIFFERENTIAL JSON:
{differential_json}

PATIENT EVIDENCE SNIPPETS (N/L/M only):
{evidence_snips}

QUESTION_TEMPLATES (use as inspiration):
{templates_json}
"""
