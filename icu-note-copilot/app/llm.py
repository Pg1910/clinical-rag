import httpx, os, json
from app.retrieval import global_retrieve, local_retrieve

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen3:4b"

def llm_answer(payload: dict) -> dict:
    case_id = payload.get("case_id", "latest")
    question = payload.get("question", "Give summary and differential")
    config = payload.get("config", {})
    
    # 1. Retrieve Context
    context_parts = []
    evidence_list = []
    
    # Global Retrieval
    global_res = global_retrieve({"case_id": case_id, "question": question})
    if "results" in global_res:
        context_parts.append("Global Context (SOAP):")
        for category, items in global_res["results"].items():
            if items:
                context_parts.append(f"[{category} Section]:")
                for item in items:
                    context_parts.append(f"- {item.get('text', '')}")
                    evidence_list.append(item)

    # Local Retrieval
    local_res = local_retrieve({"case_id": case_id, "question": question})
    if "results" in local_res:
        context_parts.append("\nLocal Context:")
        for category, items in local_res["results"].items():
            if items:
                for item in items:
                    context_parts.append(f"- {item.get('text', '')}")
                    evidence_list.append(item)

    context_str = "\n".join(context_parts)

    # 2. Prompt Engineering
    system_instruction = (
        "You are an expert clinical assistant. Analyze the provided clinical context to answer the question. "
        "Provide a detailed, extensive summary (at least 5-8 bullet points) covering patient history, symptoms, relevant findings, and assessment. "
        "Return the response in strictly valid JSON format with the following structure: "
        "{\"summary\": [\"detailed point 1\", \"detailed point 2\"], \"differential\": {\"support\": [], \"against\": [], \"missing\": []}}"
    )
    
    prompt = f"{system_instruction}\n\nCase ID: {case_id}\nQuestion: {question}\n\nContext:\n{context_str}\n\nResponse:"

    # 3. Call Ollama
    report_data = None
    raw_text = ""
    try:
        response = httpx.post(
            OLLAMA_URL, 
            json={
                "model": MODEL, 
                "prompt": prompt, 
                "stream": False,
                "options": {"temperature": 0.2, "num_ctx": 4096},
                # "format": "json"  # Disabled to avoid "improper format stop reason" errors
            },
            timeout=httpx.Timeout(600.0, connect=10.0) # 10 minute timeout for local CPU
        )
        response.raise_for_status()
        res_json = response.json()
        raw_text = res_json.get("response", "")
        
        # Parse JSON from LLM - More robust approach
        try:
            import re
            # Try to find the first '{' and last '}'
            match = re.search(r"(\{.*\})", raw_text, re.DOTALL)
            if match:
                clean_text = match.group(1)
                report_data = json.loads(clean_text)
            else:
                # Fallback to current simplistic cleaning if regex fails
                clean_text = raw_text.strip()
                if clean_text.startswith("```json"): clean_text = clean_text[7:]
                if clean_text.startswith("```"): clean_text = clean_text[3:]
                if clean_text.endswith("```"): clean_text = clean_text[:-3]
                report_data = json.loads(clean_text)
        except Exception as parse_err:
            print(f"JSON Parsing Error: {parse_err}")
            report_data = {
                "summary": [raw_text],
                "differential": {"support": [], "against": [], "missing": []}
            }
            
    except Exception as e:
        print(f"LLM Error: {repr(e)}")
        raw_text = f"Error: {str(e)}"
        report_data = {
            "summary": [f"Could not generate report due to error: {str(e)}"],
            "differential": {"support": [], "against": [], "missing": []}
        }

    # 4. Construct Response
    return {
        "assistant_message": raw_text, 
        "report": report_data,
        "evidence": evidence_list, 
        "verification": {"ok": True if raw_text else False, "findings": []}, 
        "trace": {
            "global_run": global_res,
            "local_run": local_res,
            "llm_prompt_len": len(prompt)
        },
        "latency_ms": {
             "global": 100, # Simulated or measured could be better
             "local": 50,
             "llm": 2000, 
             "verify": 10
        }
    }
