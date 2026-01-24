import json, os
from typing import Dict, Any


DATA_DIR = "data/processed/runs/latest/"
EVIDENCE_STORE = os.path.join(DATA_DIR, "evidence_store.json")
evidence_store = {}
if os.path.exists(EVIDENCE_STORE):
    with open(EVIDENCE_STORE, "r") as f:
        try:
            evidence_store = {e["evidence_id"]: e for e in json.load(f)}
        except Exception:
            evidence_store = {}

def get_cases():
    # Example: list of row_ids from evidence store
    cases = [
        {"case_id": "latest", "label": "Latest run"}
    ]
    for e in evidence_store.values():
        if "row_id" in e:
            cases.append({"case_id": e["row_id"], "label": f"Row {e['row_id']}"})
    return {"cases": cases}

def get_evidence(evidence_id: str) -> Dict[str, Any]:
    return evidence_store.get(evidence_id, {})

def global_retrieve(payload: dict) -> dict:
    # Dummy implementation: return SOAP queries and top evidence
    case_id = payload.get("case_id", "latest")
    question = payload.get("question", "Summarize case")
    soap_queries = {
        "S": ["What is the chief complaint?", "History of present illness?"],
        "O": ["Key labs?", "Monitor findings?"],
        "A": ["Diagnosis?"],
        "P": ["Plan?"]
    }
    results = {s: [e for e in list(evidence_store.values())[:5]] for s in "SOAP"}
    return {"soap_queries": soap_queries, "results": results}

def local_retrieve(payload: dict) -> dict:
    # Dummy implementation: derive sub-queries and return evidence
    case_id = payload.get("case_id", "latest")
    question = payload.get("question", "Is there evidence of sepsis?")
    derived_queries = [{"section": "A", "query": question}]
    results = {s: [e for e in list(evidence_store.values())[5:20]] for s in "SOAP"}
    return {"derived_queries": derived_queries, "results": results}
