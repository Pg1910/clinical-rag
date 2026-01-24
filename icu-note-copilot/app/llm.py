import httpx, os, json
from pydantic import BaseModel, ValidationError

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "gemma3:4b"

def llm_answer(payload: dict) -> dict:
    case_id = payload.get("case_id", "latest")
    question = payload.get("question", "Give summary and differential")
    use_global = payload.get("use_global", True)
    use_local = payload.get("use_local", True)
    # Compose prompt (simplified)
    prompt = f"Case: {case_id}\nQuestion: {question}\nUse global: {use_global}\nUse local: {use_local}"
    # Call Ollama
    response = httpx.post(OLLAMA_URL, json={"model": MODEL, "prompt": prompt, "options": {"temperature": 0.2, "top_p": 0.9, "num_ctx": 4096}})
    text = response.json().get("response", "")
    # Dummy report
    report = {"summary": ["Patient is stable."], "differential": {"support": [], "against": [], "missing": []}}
    verification = {"ok": True, "findings": []}
    trace = {"global": {}, "local": {}, "llm": {"model": MODEL, "temperature": 0.2, "num_ctx": 4096}}
    latency_ms = {"global": 12, "local": 25, "llm": 1200, "verify": 5}
    return {"assistant_message": text, "report": report, "verification": verification, "trace": trace, "latency_ms": latency_ms}
