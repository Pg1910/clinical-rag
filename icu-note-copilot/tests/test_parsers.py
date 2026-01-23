"""Tests for document parsers"""
from pathlib import Path
import json

def test_processed_files_exist():
    root = Path(__file__).resolve().parents[1]
    processed = root / "data" / "processed"
    assert (processed / "narrative_spans.jsonl").exists()
    assert (processed / "monitor.jsonl").exists()
    assert (processed / "labs.jsonl").exists()
    assert (processed / "codebook.jsonl").exists()
    assert (processed / "domain.jsonl").exists()

def test_evidence_id_uniqueness():
    root = Path(__file__).resolve().parents[1]
    processed = root / "data" / "processed"
    ids = set()
    for fname in ["narrative_spans.jsonl","monitor.jsonl","labs.jsonl","codebook.jsonl","domain.jsonl"]:
        with (processed / fname).open("r", encoding="utf-8") as f:
            for line in f:
                obj = json.loads(line)
                eid = obj["evidence_id"]
                assert eid not in ids, f"duplicate evidence_id: {eid}"
                ids.add(eid)
