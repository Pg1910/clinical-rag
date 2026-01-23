"""FastAPI application for ICU Copilot Demo."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Paths
ROOT = Path(__file__).resolve().parents[4]
DATA_DIR = ROOT / "data"
INDICES_DIR = DATA_DIR / "indices"
RUNS_DIR = DATA_DIR / "processed" / "runs" / "latest"

app = FastAPI(
    title="ICU Copilot API",
    description="Clinical Decision Support API for ICU Notes",
    version="1.0.0",
)

# CORS for Streamlit/frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def load_json(path: Path) -> dict:
    """Load JSON file safely."""
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {path.name}")
    return json.loads(path.read_text(encoding="utf-8"))


# === Response Models ===
class EvidenceResponse(BaseModel):
    evidence_id: str
    evidence_type: str
    source_file: str
    line_start: int
    line_end: int
    raw_text: str


class HealthResponse(BaseModel):
    status: str
    version: str
    data_available: bool


# === Endpoints ===

@app.get("/", response_class=HTMLResponse)
async def root():
    """API landing page."""
    return """
    <html>
        <head><title>ICU Copilot API</title></head>
        <body style="font-family: sans-serif; max-width: 800px; margin: 50px auto;">
            <h1>🏥 ICU Copilot API</h1>
            <p>Clinical Decision Support API for ICU Notes</p>
            <h2>Endpoints:</h2>
            <ul>
                <li><a href="/docs">/docs</a> - Interactive API documentation</li>
                <li><a href="/health">/health</a> - Health check</li>
                <li><a href="/report">/report</a> - Get full report JSON</li>
                <li><a href="/summary">/summary</a> - Get ICU summary</li>
                <li><a href="/differential">/differential</a> - Get differential diagnoses</li>
                <li><code>/evidence/{id}</code> - Get specific evidence by ID</li>
                <li><a href="/report.md">/report.md</a> - Download Markdown report</li>
            </ul>
        </body>
    </html>
    """


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    report_exists = (RUNS_DIR / "report.json").exists()
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        data_available=report_exists,
    )


@app.get("/report")
async def get_report():
    """
    Get the full clinical decision support report.
    
    Returns:
        Complete report JSON including summary, differential, questions, and action items.
    """
    return load_json(RUNS_DIR / "report.json")


@app.get("/summary")
async def get_summary():
    """
    Get the ICU structured summary.
    
    Returns:
        ICU summary organized by organ systems.
    """
    report = load_json(RUNS_DIR / "report.json")
    return {"summary": report.get("summary", [])}


@app.get("/differential")
async def get_differential():
    """
    Get the differential diagnosis list.
    
    Returns:
        Ranked differential diagnoses with support, against, and missing items.
    """
    report = load_json(RUNS_DIR / "report.json")
    return {"differential": report.get("differential", [])}


@app.get("/questions")
async def get_questions():
    """
    Get clarifying questions and action items.
    
    Returns:
        Prioritized clarifying questions and clinical action items.
    """
    report = load_json(RUNS_DIR / "report.json")
    return {
        "clarifying_questions": report.get("clarifying_questions", []),
        "action_items": report.get("action_items", []),
    }


@app.get("/evidence/{evidence_id}", response_model=EvidenceResponse)
async def get_evidence(evidence_id: str):
    """
    Get evidence details by ID.
    
    Args:
        evidence_id: Evidence ID (e.g., N000001, L000040, M000001)
    
    Returns:
        Evidence record with source file, line range, and raw text.
    """
    store = load_json(INDICES_DIR / "evidence_store.json")
    
    if evidence_id not in store:
        raise HTTPException(status_code=404, detail=f"Evidence ID not found: {evidence_id}")
    
    record = store[evidence_id]
    return EvidenceResponse(
        evidence_id=evidence_id,
        evidence_type=record.get("evidence_type", "unknown"),
        source_file=record.get("source_file", "unknown"),
        line_start=record.get("line_start", 0),
        line_end=record.get("line_end", 0),
        raw_text=record.get("raw_text", ""),
    )


@app.get("/evidence")
async def list_evidence(prefix: Optional[str] = None, limit: int = 50):
    """
    List available evidence IDs.
    
    Args:
        prefix: Filter by prefix (N, L, M, D, C)
        limit: Maximum number of results
    
    Returns:
        List of evidence IDs with basic info.
    """
    store = load_json(INDICES_DIR / "evidence_store.json")
    
    results = []
    for eid, record in store.items():
        if prefix and not eid.startswith(prefix.upper()):
            continue
        
        results.append({
            "evidence_id": eid,
            "evidence_type": record.get("evidence_type", "unknown"),
            "source_file": record.get("source_file", "unknown"),
            "text_preview": record.get("raw_text", "")[:100],
        })
        
        if len(results) >= limit:
            break
    
    return {"count": len(results), "evidence": results}


@app.get("/report.md")
async def get_markdown_report():
    """
    Download the Markdown report.
    
    Returns:
        Markdown file for printing/sharing.
    """
    md_path = RUNS_DIR / "report.md"
    if not md_path.exists():
        raise HTTPException(status_code=404, detail="Markdown report not generated. Run export_report.py first.")
    
    return FileResponse(
        md_path,
        media_type="text/markdown",
        filename="icu_report.md",
    )


@app.get("/patient_state")
async def get_patient_state():
    """
    Get the extracted patient state.
    
    Returns:
        Structured patient state with diagnoses, procedures, labs, etc.
    """
    return load_json(RUNS_DIR / "patient_state.json")


@app.get("/quality")
async def get_quality_metrics():
    """
    Get quality gate results.
    
    Returns:
        Quality scores and metrics for summary and differential.
    """
    return load_json(RUNS_DIR / "quality_gate.json")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

