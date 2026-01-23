"""Logging configuration for ICU Copilot"""
from __future__ import annotations

from rich.console import Console
from rich.logging import RichHandler
import logging


def setup_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=Console(stderr=True), rich_tracebacks=True)],
    )
