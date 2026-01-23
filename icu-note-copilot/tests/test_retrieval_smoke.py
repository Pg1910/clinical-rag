from pathlib import Path
from icu_copilot.rag.retrieve import HybridRetriever

def test_retrieval_returns_results():
    r = HybridRetriever(Path("data/indices"))
    res = r.hybrid_search("FiO2", top_k=5)
    assert len(res) > 0

def test_evidence_lookup_works():
    r = HybridRetriever(Path("data/indices"))
    res = r.hybrid_search("BUN 72", top_k=5)
    assert len(res) > 0
    rec = r.get_evidence(res[0].evidence_id)
    assert "raw_text" in rec
