"""Index building and management"""
from __future__ import annotations

import json
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

from icu_copilot.config import SETTINGS


@dataclass(frozen=True)
class EvidenceDoc:
    evidence_id: str
    text: str
    meta: dict


def _tokenize(text: str) -> list[str]:
    return [t for t in text.lower().split() if t.strip()]


def load_jsonl(path: Path) -> list[dict]:
    out = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            out.append(json.loads(line))
    return out


def build_evidence_corpus(processed_dir: Path) -> tuple[list[EvidenceDoc], dict[str, dict]]:
    """
    Returns:
      docs: list of documents for retrieval (text)
      store: evidence_id -> full record (for /evidence lookup and audit)
    """
    # Legacy ICU files
    files = [
        processed_dir / "narrative_spans.jsonl",
        processed_dir / "labs.jsonl",
        processed_dir / "monitor.jsonl",
        processed_dir / "codebook.jsonl",
        processed_dir / "domain.jsonl",
        processed_dir / "flowsheet.jsonl",
        # CSV-derived evidence files
        processed_dir / "csv_summaries.jsonl",
        processed_dir / "csv_notes.jsonl",
        processed_dir / "csv_full_notes.jsonl",
        processed_dir / "csv_conversations.jsonl",
    ]
    docs: list[EvidenceDoc] = []
    store: dict[str, dict] = {}
    for fp in files:
        if not fp.exists():
            continue
        rows = load_jsonl(fp)
        for r in rows:
            eid = r.get("evidence_id", r.get("id", ""))
            if not eid:
                continue
            store[eid] = r
            txt = r.get("raw_text", r.get("text", ""))
            meta = {
                "source_file": r.get("source_file", fp.name),
                "evidence_type": r.get("evidence_type", ""),
                "row_id": r.get("row_id"),
                "field": r.get("field"),
            }
            docs.append(EvidenceDoc(evidence_id=eid, text=txt, meta=meta))
    return docs, store


def build_and_save_indices(processed_dir: Path, indices_dir: Path) -> None:
    indices_dir.mkdir(parents=True, exist_ok=True)

    docs, store = build_evidence_corpus(processed_dir)
    texts = [d.text for d in docs]
    ids = [d.evidence_id for d in docs]

    # BM25
    tokenized = [_tokenize(t) for t in texts]
    bm25 = BM25Okapi(tokenized)

    # Embeddings + FAISS
    model = SentenceTransformer(SETTINGS.embed_model)
    emb = model.encode(texts, batch_size=64, show_progress_bar=True, normalize_embeddings=True)
    emb = np.asarray(emb, dtype=np.float32)

    import faiss

    index = faiss.IndexFlatIP(emb.shape[1])
    index.add(emb)

    # Persist artifacts
    (indices_dir / "doc_ids.json").write_text(json.dumps(ids, indent=2), encoding="utf-8")

    with (indices_dir / "bm25.pkl").open("wb") as f:
        pickle.dump(bm25, f)

    faiss.write_index(index, str(indices_dir / "faiss.index"))

    with (indices_dir / "evidence_store.json").open("w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)
