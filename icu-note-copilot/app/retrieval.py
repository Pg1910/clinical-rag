import json
import os
from typing import Dict, Any, List

# Paths
DATA_DIR = os.path.join(os.path.dirname(__file__), "../data")
NOTES_PATH = os.path.join(DATA_DIR, "clinical_notes_100.jsonl")

# In-memory store
cases_store = {}

def load_data():
    """Loads clinical notes into memory on startup."""
    global cases_store
    if not os.path.exists(NOTES_PATH):
        print(f"Warning: {NOTES_PATH} not found.")
        return

    print(f"Loading data from {NOTES_PATH}...")
    try:
        with open(NOTES_PATH, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                    idx = str(obj.get("idx", ""))
                    if idx:
                        cases_store[idx] = obj
                except json.JSONDecodeError:
                    continue
        print(f"Loaded {len(cases_store)} cases.")
    except Exception as e:
        print(f"Error loading data: {e}")

# Load immediately on import (simple for this scale)
load_data()

def get_cases() -> Dict[str, List[Dict[str, str]]]:
    """Returns list of available cases."""
    case_list = []
    # Sort by ID for consistent order
    for idx in sorted(cases_store.keys(), key=lambda x: int(x) if x.isdigit() else x):
        # Create a label, e.g., "Case 155216: A sixteen year-old..."
        # Truncate note for label
        note_snippet = cases_store[idx].get("note", "")[:50] + "..."
        label = f"Case {idx}: {note_snippet}"
        case_list.append({"case_id": idx, "label": label})
    
    return {"cases": case_list}

def get_case_data(case_id: str) -> Dict[str, Any]:
    return cases_store.get(case_id, {})

def get_evidence(evidence_id: str) -> Dict[str, Any]:
    # In a real system, evidence might be distinct chunks. 
    # For now, we simulate evidence as the full note or specific parts if available.
    # If evidence_id matches a case_id, return the full note as "evidence"
    if evidence_id in cases_store:
        val = cases_store[evidence_id]
        return {
            "evidence_id": evidence_id,
            "text": val.get("full_note") or val.get("note"),
            "source": f"clinical_notes_100.jsonl (Case {evidence_id})"
        }
    return {"evidence_id": evidence_id, "text": "Evidence not found."}

def global_retrieve(payload: dict) -> dict:
    case_id = str(payload.get("case_id"))
    question = payload.get("question")
    
    case_data = cases_store.get(case_id)
    if not case_data:
        return {"error": "Case not found"}

    # Simulate retrieval results using the actual case text
    # In a real RAG, this would query a vector DB.
    # Here, we just return the "Note" as the top evidence for "S" (Subjective)
    
    note_text = case_data.get("note", "")
    
    # Simple chunking for "evidence"
    chunks = [note_text[i:i+500] for i in range(0, len(note_text), 500)]
    
    results = {
        "S": [{"id": case_id, "text": chunks[0] if chunks else ""}],
        "O": [{"id": case_id, "text": chunks[1] if len(chunks)>1 else ""}],
        "A": [],
        "P": []
    }
    
    soap_queries = {
        "S": ["What is the patient history?"],
        "O": ["What are the objective findings?"],
        "A": ["Assessment?"],
        "P": ["Plan?"]
    }

    return {"soap_queries": soap_queries, "results": results, "evidence_count": len(chunks)}

def local_retrieve(payload: dict) -> dict:
    case_id = str(payload.get("case_id"))
    question = payload.get("question")
    
    # Just return the case note as evidence for now
    return {
        "derived_queries": [{"section": "Custom", "query": question}],
        "results": {
            "Local": [{"id": case_id, "text": f"Simulated local result for {question}"}]
        }
    }
