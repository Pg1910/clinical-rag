"""Main pipeline execution"""
from __future__ import annotations

import logging
from pathlib import Path

from icu_copilot.logging_conf import setup_logging
from icu_copilot.pipeline.steps import ingest_all


def main() -> None:
    setup_logging(logging.INFO)
    repo_root = Path(__file__).resolve().parents[3]
    raw_dir = repo_root / "data" / "raw"
    processed_dir = repo_root / "data" / "processed"

    out = ingest_all(raw_dir=raw_dir, processed_dir=processed_dir)
    logging.info("Parsed and wrote artifacts:")
    for k, p in out.items():
        logging.info(f"  {k:10s} -> {p}")


if __name__ == "__main__":
    main()
