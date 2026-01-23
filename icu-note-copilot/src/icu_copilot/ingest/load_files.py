"""File loading functionality"""
from __future__ import annotations

from pathlib import Path


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def list_raw_files(raw_dir: Path) -> list[Path]:
    return sorted([p for p in raw_dir.glob("*") if p.is_file()])
