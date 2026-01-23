"""Retrieval functionality"""
from __future__ import annotations

import json
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

from icu_copilot.config import SETTINGS


@dataclass(frozen=True)
class RetrievalResult:
    evidence_id: str
    score: float
    text: str


def _tokenize(text: str) -> list[str]:
    return [t for t in text.lower().split() if t.strip()]


class HybridRetriever:
    def __init__(self, indices_dir: Path):
        self.indices_dir = indices_dir
        self.doc_ids: list[str] = json.loads((indices_dir / "doc_ids.json").read_text(encoding="utf-8"))

        with (indices_dir / "bm25.pkl").open("rb") as f:
            self.bm25: BM25Okapi = pickle.load(f)

        self.store: dict = json.loads((indices_dir / "evidence_store.json").read_text(encoding="utf-8"))

        import faiss

        self.faiss = faiss.read_index(str(indices_dir / "faiss.index"))
        self.embedder = SentenceTransformer(SETTINGS.embed_model)

    def get_evidence(self, evidence_id: str) -> dict:
        return self.store[evidence_id]

    def hybrid_search(self, query: str, top_k: int | None = None) -> list[RetrievalResult]:
        k = top_k or SETTINGS.top_k

        # BM25 scores
        bm_scores = self.bm25.get_scores(_tokenize(query)).astype(np.float32)
        bm_scores = bm_scores / (bm_scores.max() + 1e-9)

        # Vector scores
        q_emb = self.embedder.encode([query], normalize_embeddings=True)
        q_emb = np.asarray(q_emb, dtype=np.float32)
        vec_scores, vec_idx = self.faiss.search(q_emb, k=min(max(k * 5, 20), len(self.doc_ids)))
        vec_scores = vec_scores[0]
        vec_idx = vec_idx[0]

        vec_norm = (vec_scores - vec_scores.min()) / ((vec_scores.max() - vec_scores.min()) + 1e-9)

        # Combine: weighted sum
        # Prefer BM25 a bit for numbers/labs; vector helps semantic.
        combined: dict[int, float] = {}

        for i, s in enumerate(bm_scores):
            if s > 0:
                combined[i] = combined.get(i, 0.0) + 0.55 * float(s)

        for j, doc_i in enumerate(vec_idx):
            if doc_i < 0:
                continue
            combined[doc_i] = combined.get(doc_i, 0.0) + 0.45 * float(vec_norm[j])

        ranked = sorted(combined.items(), key=lambda x: x[1], reverse=True)[:k]

        out: list[RetrievalResult] = []
        for doc_i, s in ranked:
            eid = self.doc_ids[doc_i]
            rec = self.store[eid]
            out.append(RetrievalResult(evidence_id=eid, score=float(s), text=rec.get("raw_text", "")))

        return out
