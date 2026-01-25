from fastapi import FastAPI, Request, Response, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.retrieval import global_retrieve, local_retrieve, get_cases
from app.llm import llm_answer
from app.metrics import compute_bleu, get_metrics
import os

app = FastAPI()

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# Simple Hardcoded Credentials
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "password"
SESSION_COOKIE = "rag_session"

def get_current_user(request: Request):
    """Dependency to check if the user is authenticated via cookie."""
    session = request.cookies.get(SESSION_COOKIE)
    if session != "authenticated":
        return None
    return "admin"

@app.get("/login", response_class=HTMLResponse)
def login_get(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
def login_post(username: str = Form(...), password: str = Form(...)):
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(key=SESSION_COOKIE, value="authenticated")
        return response
    return templates.TemplateResponse("login.html", {"request": {}, "error": "Invalid credentials"})

@app.get("/logout")
def logout():
    response = RedirectResponse(url="/login")
    response.delete_cookie(SESSION_COOKIE)
    return response

@app.get("/", response_class=HTMLResponse)
def index(request: Request, user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/cases")
def api_cases(user: str = Depends(get_current_user)):
    if not user: raise HTTPException(status_code=401)
    return JSONResponse(get_cases())

@app.post("/api/retrieve/global")
def api_retrieve_global(payload: dict, user: str = Depends(get_current_user)):
    if not user: raise HTTPException(status_code=401)
    return JSONResponse(global_retrieve(payload))

@app.post("/api/retrieve/local")
def api_retrieve_local(payload: dict, user: str = Depends(get_current_user)):
    if not user: raise HTTPException(status_code=401)
    return JSONResponse(local_retrieve(payload))

@app.post("/api/llm/answer")
def api_llm_answer(payload: dict, user: str = Depends(get_current_user)):
    if not user: raise HTTPException(status_code=401)
    return JSONResponse(llm_answer(payload))

@app.get("/api/evidence/{evidence_id}")
def api_evidence(evidence_id: str, user: str = Depends(get_current_user)):
    if not user: raise HTTPException(status_code=401)
    from app.retrieval import get_evidence
    return JSONResponse(get_evidence(evidence_id))

@app.post("/api/metrics/bleu")
def api_bleu(payload: dict, user: str = Depends(get_current_user)):
    if not user: raise HTTPException(status_code=401)
    return JSONResponse(compute_bleu(payload))

@app.get("/api/metrics")
def api_metrics(user: str = Depends(get_current_user)):
    if not user: raise HTTPException(status_code=401)
    return JSONResponse(get_metrics())
