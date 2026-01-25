# Clinical RAG Copilot — Evidence-First Decision Support

A hospital-grade **Retrieval-Augmented Generation (RAG)** system for clinical data that produces **auditable summaries, differentials, and clarifying questions** with strict evidence traceability.

> **Core principle:**  
> *No clinical statement is generated without explicit, traceable evidence.*

---

## 🔍 Problem Statement

Clinical data is:
- Highly **unstructured** (notes, conversations, free text)
- **Fragmented** across formats (TXT, CSV, JSON, labs, monitors)
- Difficult to summarize **safely** using standard LLMs due to hallucinations and lack of traceability

Most LLM-based clinical tools:
- Mix background medical knowledge with patient-specific facts
- Do not expose retrieval or reasoning steps
- Are hard to audit or deploy safely in hospital environments

---

## 💡 Our Solution

We built a **two-stage RAG pipeline** with:

### 1. Global Retrieval Context (SOAP-Structured)
- Uses deterministic **SOAP-style question templates**
- Creates a **stable, low-token global context**
- Ensures consistent extraction across diverse data sources

### 2. Local Retrieval Context (Evidence-Heavy)
- Hybrid **BM25 + Vector (FAISS)** retrieval
- Section-aware **reranking rules**
- Supplies raw evidence snippets for justification

### Output
- Structured **patient state**
- Evidence-linked **summary**
- Ranked **differential diagnosis**
- **Clarifying questions** (information gaps)
- **Action items** (information gathering only)
- Fully auditable **final report**

---

## 🧠 Architecture Overview

```

Raw Data (TXT / CSV / Notes / Conversations)
↓
Standardized Ingestion → Evidence JSONL
↓
BM25 Index + FAISS Vector Index
↓
Global Retrieval (SOAP Templates)
↓
Local Retrieval (Hybrid + Rerank)
↓
LLM Reasoning (Gemma 3–4B via Ollama)
↓
Verification + Fallback
↓
Conjoined Clinical Report (JSON)

````

---

## 📂 Supported Data Sources

- `.txt` clinical notes
- `.csv` datasets (Kaggle-style)
  - Short notes
  - Full clinical notes
  - Doctor–patient conversations
  - Structured summary JSON
- Lab values and monitoring data

All inputs are converted into a **unified evidence representation** with deterministic IDs.

---

## 🧩 Evidence Model

Each piece of evidence includes:
- `evidence_id` (deterministic)
- `evidence_type` (note, lab, conversation, summary, etc.)
- `row_id` (for CSV traceability)
- `field` (notes / full_notes / conversation / summary)
- `raw_text`

This enables:
- Full provenance
- Click-through inspection
- Auditability

---

## 🤖 LLM Configuration

- **Model:** `gemma3:4b` (via Ollama)
- **Deployment:** Fully local
- **VRAM requirement:** ~4GB
- **Temperature:** 0.2
- **Context window:** 4096 tokens

LLM usage is **constrained and validated**:
- JSON schema enforcement
- Retry + repair logic
- Deterministic fallback if generation fails

---

## 🛡️ Safety & Verification

The system enforces:
- No unsupported claims
- No domain/background text used as patient facts
- Evidence-type constraints (patient vs reference)
- Deterministic validators (not just LLM checks)

If validation fails:
- The system falls back to a deterministic, safe output

---

## 📊 Metrics & Evaluation

### Retrieval Metrics
- Number of evidence chunks retrieved (global/local)
- Hybrid score distribution
- Evidence diversity (unique sources)

### Generation Metrics
- Claims with evidence / total claims
- Latency breakdown (retrieval vs LLM)

### Text Quality (Optional)
- BLEU-1 to BLEU-4 score
- Reference summary comparison (if provided)

---

## 🌐 Web Interface (FastAPI + HTML)

Features:
- Chat-style UI for summaries and Q&A
- Toggle between **global** and **local** retrieval
- Retrieval trace visualization
- Clickable evidence viewer
- Metrics dashboard
- Exportable JSON reports

---

## 🚀 Installation

```bash
git clone <repo-url>
cd clinical-rag-copilot

python -m venv venv
source venv/bin/activate

pip install -r requirements.txt
````

Ensure Ollama is installed and running:

```bash
ollama run gemma3:4b
```

---

## ▶️ Running the Pipeline

### 1. Build Indices

```bash
python -m icu_copilot.rag.build_indices
```

### 2. Run Full Clinical Pipeline

```bash
python -m icu_copilot.pipeline.run_llm
```

### 3. Generate Conjoined Report

```bash
python -m icu_copilot.pipeline.compose_report
```

Artifacts are written to:

```
data/processed/runs/latest/
```

---

## 🌐 Run the Web Demo

```bash
uvicorn app.main:app --reload --port 8000
```

Open:

```
http://localhost:8000
```

---

## 📄 Output Artifacts

* `patient_state.json`
* `summary.json`
* `differential.json`
* `report.json`
* `verification_*.json`

Each output is:

* Machine-readable
* Human-auditable
* Evidence-linked

---

## 🎯 Target Users

* Clinicians (ICU / inpatient settings)
* Clinical researchers
* Hospital IT & innovation teams
* AI governance & compliance reviewers

---

## 🌟 Why This Is Different

* Two-stage retrieval (Global + Local)
* SOAP-aware reasoning
* Evidence-type separation
* Deterministic safety guarantees
* Fully local deployment
* Transparent, explainable outputs

> This is **not** a generic medical chatbot.
> This is **evidence-first clinical decision support**.

---

## 🔮 Future Work

* Temporal trend visualization
* Multi-patient cohort analysis
* EHR integration
* Clinician feedback loop
* Active learning for retrieval refinement

---

## ⚠️ Disclaimer

This system is a **clinical decision-support prototype**.
It does **not** provide medical advice and must not replace professional clinical judgment.

---

Tell me what you want next.
```
