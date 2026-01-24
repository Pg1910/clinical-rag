import numpy as np
from collections import Counter

def compute_bleu(payload: dict) -> dict:
    # Simple BLEU implementation
    generated = payload.get("generated", "").split()
    reference = payload.get("reference", "").split()
    def ngram_counts(tokens, n):
        return Counter([tuple(tokens[i:i+n]) for i in range(len(tokens)-n+1)])
    def bleu_n(g, r, n):
        g_ngrams = ngram_counts(g, n)
        r_ngrams = ngram_counts(r, n)
        overlap = sum((g_ngrams & r_ngrams).values())
        total = max(sum(g_ngrams.values()), 1)
        return overlap / total
    bleu1 = bleu_n(generated, reference, 1)
    bleu2 = bleu_n(generated, reference, 2)
    bleu3 = bleu_n(generated, reference, 3)
    bleu4 = bleu_n(generated, reference, 4)
    bleu = np.mean([bleu1, bleu2, bleu3, bleu4])
    return {"bleu1": bleu1, "bleu2": bleu2, "bleu3": bleu3, "bleu4": bleu4, "bleu": bleu}

def get_metrics():
    # Dummy metrics
    return {"latency": {"global": 12, "local": 25, "llm": 1200, "verify": 5}, "retrieval": {"docs_global": 10, "docs_local": 20, "avg_hybrid": 0.45, "diversity": 5}, "generation": {"token_estimate": 120, "claims_with_evidence": 8, "total_claims": 10}}
