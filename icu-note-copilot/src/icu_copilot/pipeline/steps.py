"""Individual pipeline steps"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from icu_copilot.ingest.load_files import read_text
from icu_copilot.ingest.parsers import (
    parse_narrative,
    parse_labs,
    parse_monitor_codebook,
    parse_monitor_data,
    parse_domain_description,
    codebook_map,
)
from icu_copilot.ingest.schemas import EvidenceRecord
from icu_copilot.ingest.validate import ensure_unique_ids


def write_jsonl(path: Path, records: Iterable[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r.model_dump(mode="json"), ensure_ascii=False) + "\n")


def ingest_all(raw_dir: Path, processed_dir: Path) -> dict[str, Path]:
    """
    Expects files in raw_dir. Filenames can vary; we match by keywords.
    """
    files = {p.name.lower(): p for p in raw_dir.glob("*") if p.is_file()}

    def find_one(*keywords: str) -> Path:
        for name, p in files.items():
            if all(k in name for k in keywords):
                return p
        raise FileNotFoundError(f"Could not find file with keywords: {keywords}")

    patient_desc = find_one("patient")
    monitor_codes = find_one("monitor", "code")
    monitor_data = find_one("monitor", "data")
    labs = find_one("lab")
    # flowsheet optional (may duplicate labs)
    flowsheet = None
    for name, p in files.items():
        if "flowsheet" in name:
            flowsheet = p
            break
    domain = find_one("domain")

    # Parse
    narrative_recs = parse_narrative(read_text(patient_desc), patient_desc.name)
    codebook_recs = parse_monitor_codebook(read_text(monitor_codes), monitor_codes.name)
    cb_map = codebook_map(codebook_recs)
    monitor_recs = parse_monitor_data(read_text(monitor_data), monitor_data.name, cb_map)
    lab_recs = parse_labs(read_text(labs), labs.name)
    domain_recs = parse_domain_description(read_text(domain), domain.name)

    all_recs: list[EvidenceRecord] = []
    all_recs.extend(narrative_recs)
    all_recs.extend(codebook_recs)
    all_recs.extend(monitor_recs)
    all_recs.extend(lab_recs)
    all_recs.extend(domain_recs)

    ensure_unique_ids(all_recs)

    out_paths = {
        "narrative": processed_dir / "narrative_spans.jsonl",
        "codebook": processed_dir / "codebook.jsonl",
        "monitor": processed_dir / "monitor.jsonl",
        "labs": processed_dir / "labs.jsonl",
        "domain": processed_dir / "domain.jsonl",
    }

    write_jsonl(out_paths["narrative"], narrative_recs)
    write_jsonl(out_paths["codebook"], codebook_recs)
    write_jsonl(out_paths["monitor"], monitor_recs)
    write_jsonl(out_paths["labs"], lab_recs)
    write_jsonl(out_paths["domain"], domain_recs)

    # If flowsheet exists and is not identical, keep separately (optional)
    if flowsheet is not None:
        flow_recs = parse_labs(read_text(flowsheet), flowsheet.name)
        out_paths["flowsheet"] = processed_dir / "flowsheet.jsonl"
        write_jsonl(out_paths["flowsheet"], flow_recs)

    return out_paths
