from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import uvicorn
import json

app = FastAPI()

# Mount static directory for HTML/JS/CSS
app.mount("/static", StaticFiles(directory="static"), name="static")

# Load available row IDs from JSONL
DATA_PATH = Path("../data/clinical_notes_100.jsonl")
ROW_IDS = []
if DATA_PATH.exists():
    with open(DATA_PATH) as f:
        for line in f:
            try:
                obj = json.loads(line)
                ROW_IDS.append(int(obj.get("idx")))
            except:
                continue

@app.get("/", response_class=HTMLResponse)
def index():
    with open("static/index.html") as f:
        return f.read()

@app.get("/api/rows")
def get_rows():
    return {"rows": ROW_IDS}

@app.get("/api/case/{row_id}")
def get_case(row_id: int):
    from icu_copilot.pipeline.run_case import CasePipeline
    from pathlib import Path
    indices_dir = Path("../data/indices")
    csv_path = DATA_PATH
    pipeline = CasePipeline(indices_dir=indices_dir, csv_path=csv_path)
    report = pipeline.run(row_id)
    return JSONResponse(content={
        "row_id": row_id,
        "soap_summary": report.soap_summary,
        "differential": report.differential,
        "evidence_used": report.evidence_used,
    })

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
