import json
from pathlib import Path

processed = Path("data/processed")
evidence_files = [
    "narrative_spans.jsonl",
    "monitor.jsonl",
    "labs.jsonl",
    "codebook.jsonl",
    "domain.jsonl",
    "csv_conversations.jsonl",
    "csv_full_notes.jsonl",
    "csv_notes.jsonl",
    "csv_summaries.jsonl"
]

evidence = []
for fname in evidence_files:
    fpath = processed / fname
    if fpath.exists():
        with open(fpath, "r", encoding="utf-8") as f:
            for line in f:
                obj = json.loads(line)
                evidence.append(obj)

with open(processed / "runs/latest/evidence_store.json", "w", encoding="utf-8") as f:
    json.dump(evidence, f, ensure_ascii=False, indent=2)

print(f"Wrote {len(evidence)} evidence items to {processed / 'runs/latest/evidence_store.json'}")
