from __future__ import annotations

QUESTION_TEMPLATES = [
    {
        "id": "infection_source",
        "template": "What is the suspected source of infection (e.g., biliary, bloodstream, lung), and what evidence supports it?",
        "rationale": "Helps narrow sepsis source and competing causes of deterioration.",
    },
    {
        "id": "cultures",
        "template": "What are the blood culture results (organism, sensitivities) and timing relative to antibiotics?",
        "rationale": "Confirms pathogen, guides whether ongoing sepsis is plausible.",
    },
    {
        "id": "resp_metrics",
        "template": "What are the key respiratory severity metrics/trends (FiO2, PEEP, PIP, PaO2/SpO2 trend) over time?",
        "rationale": "Required to stage ARDS severity and distinguish ventilation issues vs disease progression.",
    },
    {
        "id": "coag_profile",
        "template": "What is the full coagulation profile trend (PT/INR, PTT, fibrinogen, platelets) and bleeding status?",
        "rationale": "Distinguishes liver-related coagulopathy from DIC and assesses severity.",
    },
    {
        "id": "hepatic_labs",
        "template": "What are liver function trends (bilirubin, AST/ALT, ammonia) and clinical signs (encephalopathy) if documented?",
        "rationale": "Corroborates liver failure trajectory and severity.",
    },
    {
        "id": "renal_status",
        "template": "What is renal function trend (BUN/Cr, urine output) and fluid balance?",
        "rationale": "Differentiates pre-renal vs intrinsic kidney injury and impacts overall severity assessment.",
    },
]
