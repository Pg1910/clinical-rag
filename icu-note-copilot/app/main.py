from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.retrieval import global_retrieve, local_retrieve, get_cases
from app.llm import llm_answer
from app.metrics import compute_bleu, get_metrics
import os

app = FastAPI()

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/cases")
def api_cases():
    return JSONResponse(get_cases())

@app.post("/api/retrieve/global")
def api_retrieve_global(payload: dict):
    return JSONResponse(global_retrieve(payload))

@app.post("/api/retrieve/local")
def api_retrieve_local(payload: dict):
    return JSONResponse(local_retrieve(payload))

@app.post("/api/llm/answer")
def api_llm_answer(payload: dict):
    return JSONResponse(llm_answer(payload))

@app.get("/api/evidence/{evidence_id}")
def api_evidence(evidence_id: str):
    from app.retrieval import get_evidence
    return JSONResponse(get_evidence(evidence_id))

@app.post("/api/metrics/bleu")
def api_bleu(payload: dict):
    return JSONResponse(compute_bleu(payload))

@app.get("/api/metrics")
def api_metrics():
    return JSONResponse(get_metrics())
