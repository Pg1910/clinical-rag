"""Document parsers for various formats"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

from .schemas import (
    NarrativeSpan,
    LabRecord,
    MonitorRecord,
    CodebookRecord,
    DomainRecord,
)

LAB_LINE_RE = re.compile(
    r"^\s*(\d{2}/\d{2}/\d{2})\s+(\d{2}:\d{2})\s+([A-Za-z0-9_]+)\s+([\-0-9.]+)\s*$"
)
MONITOR_LINE_RE = re.compile(r"^\s*(\d{2}:\d{2}:\d{2})\s+(\d+)\s+([\-0-9.]+)\s*$")
CODEBOOK_LINE_RE = re.compile(r"^\s*(\d+)\s+(.+?)\s*$")
UNIT_IN_PARENS_RE = re.compile(r"\(([^)]+)\)")


def _mk_id(prefix: str, idx: int) -> str:
    return f"{prefix}{idx:06d}"


def parse_narrative(text: str, source_file: str) -> List[NarrativeSpan]:
    lines = text.splitlines()
    spans: List[NarrativeSpan] = []
    idx = 1
    for i, line in enumerate(lines, start=1):
        if line.strip() == "":
            continue
        spans.append(
            NarrativeSpan(
                evidence_id=_mk_id("N", idx),
                source_file=source_file,
                raw_text=line.rstrip("\n"),
                line_start=i,
                line_end=i,
            )
        )
        idx += 1
    return spans


def parse_domain_description(text: str, source_file: str) -> List[DomainRecord]:
    lines = text.splitlines()
    recs: List[DomainRecord] = []
    idx = 1
    buffer: List[Tuple[int, str]] = []
    for i, line in enumerate(lines, start=1):
        if line.strip() == "":
            if buffer:
            # flush paragraph
                start = buffer[0][0]
                end = buffer[-1][0]
                para = "\n".join([x[1] for x in buffer]).strip()
                if para:
                    title = None
                    if idx == 1:
                        title = para.splitlines()[0][:120]
                    recs.append(
                        DomainRecord(
                            evidence_id=_mk_id("D", idx),
                            source_file=source_file,
                            raw_text=para,
                            line_start=start,
                            line_end=end,
                            title=title,
                        )
                    )
                    idx += 1
                buffer = []
            continue
        buffer.append((i, line))
    if buffer:
        start = buffer[0][0]
        end = buffer[-1][0]
        para = "\n".join([x[1] for x in buffer]).strip()
        if para:
            recs.append(
                DomainRecord(
                    evidence_id=_mk_id("D", idx),
                    source_file=source_file,
                    raw_text=para,
                    line_start=start,
                    line_end=end,
                    title=para.splitlines()[0][:120],
                )
            )
    return recs


def parse_monitor_codebook(text: str, source_file: str) -> List[CodebookRecord]:
    """
    Reads lines like:
      76  Volume fraction of inspired oxygen (FiO2) (%)
      85  Ventilator Data - PEEP (cm H2O)
    and also handles multi-line descriptions by attaching the next indented line(s).
    """
    lines = text.splitlines()
    recs: List[CodebookRecord] = []

    idx = 1
    pending: CodebookRecord | None = None

    for i, line in enumerate(lines, start=1):
        if line.strip() == "":
            continue

        m = CODEBOOK_LINE_RE.match(line)
        if m and not line.startswith("\t") and not line.startswith(" " * 2):
            # flush previous
            if pending is not None:
                recs.append(pending)
                idx += 1

            code = int(m.group(1))
            name = m.group(2).strip()
            unit = None
            um = UNIT_IN_PARENS_RE.search(name)
            if um:
                unit = um.group(1).strip()
            pending = CodebookRecord(
                evidence_id=_mk_id("C", idx),
                source_file=source_file,
                raw_text=line.rstrip("\n"),
                line_start=i,
                line_end=i,
                code=code,
                name=name,
                unit=unit,
            )
        else:
            # continuation line
            if pending is not None:
                pending.raw_text = pending.raw_text + "\n" + line.rstrip("\n")
                pending.line_end = i

    if pending is not None:
        recs.append(pending)

    return recs


def parse_monitor_data(text: str, source_file: str, codebook: Dict[int, Tuple[str | None, str | None]]) -> List[MonitorRecord]:
    lines = text.splitlines()
    recs: List[MonitorRecord] = []
    idx = 1
    for i, line in enumerate(lines, start=1):
        if line.strip() == "":
            continue
        m = MONITOR_LINE_RE.match(line)
        if not m:
            continue
        t = m.group(1)
        code = int(m.group(2))
        raw_val = m.group(3)
        # numeric cast
        try:
            val = float(raw_val)
            if val.is_integer():
                val = int(val)
        except ValueError:
            val = raw_val

        name, unit = codebook.get(code, (None, None))
        recs.append(
            MonitorRecord(
                evidence_id=_mk_id("M", idx),
                source_file=source_file,
                raw_text=line.rstrip("\n"),
                line_start=i,
                line_end=i,
                t=t,
                code=code,
                value=val,
                name=name,
                unit=unit,
            )
        )
        idx += 1
    return recs


def parse_labs(text: str, source_file: str) -> List[LabRecord]:
    lines = text.splitlines()
    recs: List[LabRecord] = []
    idx = 1
    for i, line in enumerate(lines, start=1):
        if line.strip() == "":
            continue
        m = LAB_LINE_RE.match(line)
        if not m:
            continue
        date_s, time_s, test, value_s = m.group(1), m.group(2), m.group(3), m.group(4)
        dt = datetime.strptime(f"{date_s} {time_s}", "%m/%d/%y %H:%M")
        try:
            value: float | str = float(value_s)
        except ValueError:
            value = value_s

        recs.append(
            LabRecord(
                evidence_id=_mk_id("L", idx),
                source_file=source_file,
                raw_text=line.rstrip("\n"),
                line_start=i,
                line_end=i,
                dt=dt,
                test=test,
                value=value,
                unit=None,
            )
        )
        idx += 1
    return recs


def codebook_map(codebook_recs: List[CodebookRecord]) -> Dict[int, Tuple[str | None, str | None]]:
    out: Dict[int, Tuple[str | None, str | None]] = {}
    for r in codebook_recs:
        if r.code is not None:
            out[r.code] = (r.name, r.unit)
    return out
