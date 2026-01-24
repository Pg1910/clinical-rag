# Clinical RAG Demo

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Features
- FastAPI backend
- HTML/JS/CSS single-page UI
- Global + Local retrieval (BM25 + FAISS hybrid)
- LLM summary via local Ollama (gemma3:4b)
- Evidence traceability, metrics, BLEU score
- Export report.json

## API Endpoints
- `/` : Main UI
- `/api/cases` : List available cases
- `/api/retrieve/global` : Global retrieval (SOAP)
- `/api/retrieve/local` : Local retrieval (sub-queries)
- `/api/llm/answer` : Full pipeline (LLM report)
- `/api/evidence/{evidence_id}` : Evidence details
- `/api/metrics/bleu` : BLEU score

## Data
- Evidence and run artifacts stored in `data/processed/runs/latest/`
