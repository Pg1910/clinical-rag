from __future__ import annotations

import logging
from pathlib import Path

from icu_copilot.logging_conf import setup_logging
from icu_copilot.rag.index_build import build_and_save_indices


def main() -> None:
    setup_logging(logging.INFO)
    repo_root = Path(__file__).resolve().parents[3]
    processed_dir = repo_root / "data" / "processed"
    indices_dir = repo_root / "data" / "indices"

    build_and_save_indices(processed_dir, indices_dir)
    logging.info(f"Indices built at: {indices_dir}")


if __name__ == "__main__":
    main()
