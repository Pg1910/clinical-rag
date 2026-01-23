#!/usr/bin/env python3
"""Generate report.md from the latest run."""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from icu_copilot.export.export_report import export_to_markdown

ROOT = Path(__file__).parent
RUNS_DIR = ROOT / "data/processed/runs/latest"
REPORT_PATH = RUNS_DIR / "report.json"
EVIDENCE_STORE = ROOT / "data/indices/evidence_store.json"
OUTPUT_PATH = RUNS_DIR / "report.md"

if __name__ == "__main__":
    try:
        output = export_to_markdown(REPORT_PATH, EVIDENCE_STORE, OUTPUT_PATH)
        print(f"✅ Exported to: {output}")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
