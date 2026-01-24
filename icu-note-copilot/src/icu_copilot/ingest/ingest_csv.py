"""
CSV Ingestion Module

Converts CSV rows into typed evidence records with deterministic IDs:
- CS_{idx}_{k} for summary_json facts
- CN_{idx}_{k} for note chunks
- CF_{idx}_{k} for full_note chunks
- CV_{idx}_{k} for conversation turns

Usage:
    python -m icu_copilot.ingest.ingest_csv --csv path/to/data.csv --out data/processed
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Iterator

from icu_copilot.logging_conf import setup_logging

logger = logging.getLogger(__name__)


# =============================================================================
# EVIDENCE TYPE DEFINITIONS
# =============================================================================

@dataclass
class EvidenceRecord:
    """A single evidence record with full provenance."""
    evidence_id: str
    evidence_type: str  # csv_summary, csv_note, csv_full_note, csv_conv
    raw_text: str
    row_id: int
    field: str  # note, full_note, conversation, summary_json
    chunk_index: int = 0
    char_start: int | None = None
    char_end: int | None = None
    metadata: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return asdict(self)


# =============================================================================
# TEXT CHUNKING UTILITIES
# =============================================================================

def chunk_text(
    text: str,
    chunk_size: int = 500,
    overlap: int = 50,
    min_chunk_size: int = 50
) -> list[tuple[str, int, int]]:
    """
    Split text into overlapping chunks.
    Returns list of (chunk_text, char_start, char_end).
    """
    if not text or len(text) < min_chunk_size:
        return [(text, 0, len(text))] if text else []
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = min(start + chunk_size, len(text))
        
        # Try to break at sentence/paragraph boundary
        if end < len(text):
            # Look for natural break points
            break_chars = ['\n\n', '\n', '. ', '? ', '! ']
            best_break = end
            for bc in break_chars:
                idx = text.rfind(bc, start + min_chunk_size, end)
                if idx > start + min_chunk_size:
                    best_break = idx + len(bc)
                    break
            end = best_break
        
        chunk = text[start:end].strip()
        if len(chunk) >= min_chunk_size:
            chunks.append((chunk, start, end))
        
        start = end - overlap if end < len(text) else len(text)
    
    return chunks


def parse_conversation(text: str) -> list[tuple[str, int, int]]:
    """
    Parse conversation into turns.
    Handles formats like:
    - "Patient: ... Doctor: ..."
    - "User: ... Assistant: ..."
    - Line-by-line dialogue
    """
    if not text:
        return []
    
    # Try to detect speaker patterns
    speaker_patterns = [
        r'(Patient|Doctor|Physician|Nurse|User|Assistant|Provider|Clinician)\s*:',
        r'(P|D|Dr|RN)\s*:',
        r'^[-*]\s*',  # Bullet points
    ]
    
    turns = []
    
    # Try speaker-based splitting first
    combined_pattern = '|'.join(f'({p})' for p in speaker_patterns[:2])
    splits = re.split(f'({combined_pattern})', text, flags=re.IGNORECASE)
    
    if len(splits) > 1:
        current_pos = 0
        current_turn = ""
        turn_start = 0
        
        for i, part in enumerate(splits):
            if part and re.match(combined_pattern, part, re.IGNORECASE):
                if current_turn.strip():
                    turns.append((current_turn.strip(), turn_start, current_pos))
                current_turn = part
                turn_start = current_pos
            elif part:
                current_turn += part
            current_pos += len(part) if part else 0
        
        if current_turn.strip():
            turns.append((current_turn.strip(), turn_start, len(text)))
    
    # Fallback to line-based if no speakers found
    if not turns:
        lines = text.split('\n')
        pos = 0
        for line in lines:
            line = line.strip()
            if len(line) > 20:  # Skip very short lines
                turns.append((line, pos, pos + len(line)))
            pos += len(line) + 1
    
    return turns if turns else [(text, 0, len(text))]


def parse_summary_json(json_str: str, row_id: int) -> list[EvidenceRecord]:
    """
    Parse summary_json field into individual fact records.
    Handles various JSON structures and extracts key-value pairs.
    """
    records = []
    
    if not json_str or not json_str.strip():
        return records
    
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.warning(f"Row {row_id}: Invalid JSON in summary_json: {e}")
        # Treat as plain text if not valid JSON
        records.append(EvidenceRecord(
            evidence_id=f"CS_{row_id}_0",
            evidence_type="csv_summary",
            raw_text=json_str[:1000],  # Truncate if needed
            row_id=row_id,
            field="summary_json",
            chunk_index=0,
        ))
        return records
    
    def extract_facts(obj: Any, prefix: str = "", idx_counter: list = None) -> None:
        """Recursively extract facts from nested structure."""
        if idx_counter is None:
            idx_counter = [0]
        
        if isinstance(obj, dict):
            for key, value in obj.items():
                new_prefix = f"{prefix}.{key}" if prefix else key
                if isinstance(value, (str, int, float, bool)) and value:
                    fact_text = f"{new_prefix}: {value}"
                    records.append(EvidenceRecord(
                        evidence_id=f"CS_{row_id}_{idx_counter[0]}",
                        evidence_type="csv_summary",
                        raw_text=fact_text,
                        row_id=row_id,
                        field="summary_json",
                        chunk_index=idx_counter[0],
                        metadata={"key": new_prefix, "value": str(value)},
                    ))
                    idx_counter[0] += 1
                elif isinstance(value, (dict, list)):
                    extract_facts(value, new_prefix, idx_counter)
        
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                if isinstance(item, (str, int, float)):
                    fact_text = f"{prefix}[{i}]: {item}"
                    records.append(EvidenceRecord(
                        evidence_id=f"CS_{row_id}_{idx_counter[0]}",
                        evidence_type="csv_summary",
                        raw_text=fact_text,
                        row_id=row_id,
                        field="summary_json",
                        chunk_index=idx_counter[0],
                        metadata={"key": f"{prefix}[{i}]", "value": str(item)},
                    ))
                    idx_counter[0] += 1
                elif isinstance(item, dict):
                    extract_facts(item, f"{prefix}[{i}]", idx_counter)
    
    extract_facts(data)
    return records


# =============================================================================
# CSV ROW PROCESSOR
# =============================================================================

@dataclass
class CSVRow:
    """Represents a single CSV row with all fields."""
    idx: int
    note: str = ""
    full_note: str = ""
    conversation: str = ""
    summary_json: str = ""
    
    @classmethod
    def from_dict(cls, row: dict, idx: int) -> "CSVRow":
        """Create from CSV row dict, handling missing fields gracefully."""
        return cls(
            idx=idx,
            note=str(row.get("note", row.get("Note", "")) or "").strip(),
            full_note=str(row.get("full_note", row.get("Full_Note", row.get("FullNote", ""))) or "").strip(),
            conversation=str(row.get("conversation", row.get("Conversation", row.get("conv", ""))) or "").strip(),
            summary_json=str(row.get("summary_json", row.get("Summary_JSON", row.get("summary", ""))) or "").strip(),
        )


def process_csv_row(row: CSVRow) -> list[EvidenceRecord]:
    """
    Convert a single CSV row into typed evidence records.
    """
    records = []
    idx = row.idx
    
    # 1. Process note field → CN_ (usually short, single chunk)
    if row.note:
        chunks = chunk_text(row.note, chunk_size=500, overlap=0)
        for k, (chunk, start, end) in enumerate(chunks):
            records.append(EvidenceRecord(
                evidence_id=f"CN_{idx}_{k}",
                evidence_type="csv_note",
                raw_text=chunk,
                row_id=idx,
                field="note",
                chunk_index=k,
                char_start=start,
                char_end=end,
            ))
    
    # 2. Process full_note → CF_ (chunked paragraphs)
    if row.full_note:
        chunks = chunk_text(row.full_note, chunk_size=500, overlap=50)
        for k, (chunk, start, end) in enumerate(chunks):
            records.append(EvidenceRecord(
                evidence_id=f"CF_{idx}_{k}",
                evidence_type="csv_full_note",
                raw_text=chunk,
                row_id=idx,
                field="full_note",
                chunk_index=k,
                char_start=start,
                char_end=end,
            ))
    
    # 3. Process conversation → CV_ (turn-by-turn)
    if row.conversation:
        turns = parse_conversation(row.conversation)
        for k, (turn, start, end) in enumerate(turns):
            records.append(EvidenceRecord(
                evidence_id=f"CV_{idx}_{k}",
                evidence_type="csv_conv",
                raw_text=turn,
                row_id=idx,
                field="conversation",
                chunk_index=k,
                char_start=start,
                char_end=end,
            ))
    
    # 4. Process summary_json → CS_ (fact extraction)
    if row.summary_json:
        summary_records = parse_summary_json(row.summary_json, idx)
        records.extend(summary_records)
    
    return records


# =============================================================================
# CSV FILE PROCESSOR
# =============================================================================

def ingest_csv_file(
    input_path: Path,
    output_dir: Path,
    row_ids: list[int] | None = None,
) -> dict[str, Path]:
    """
    Ingest CSV or JSONL file and produce JSONL evidence files.
    
    Args:
        input_path: Path to input CSV or JSONL file
        output_dir: Directory for output JSONL files
        row_ids: Optional list of specific row IDs to process
    
    Returns:
        Dict mapping evidence type to output file path
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Output files by type
    output_files = {
        "csv_summary": output_dir / "csv_summaries.jsonl",
        "csv_note": output_dir / "csv_notes.jsonl",
        "csv_full_note": output_dir / "csv_full_notes.jsonl",
        "csv_conv": output_dir / "csv_conversations.jsonl",
    }
    
    # Clear existing files
    for f in output_files.values():
        f.unlink(missing_ok=True)
    
    # File handles
    handles = {k: open(v, 'a', encoding='utf-8') for k, v in output_files.items()}
    
    try:
        # Detect file format (CSV vs JSONL)
        is_jsonl = str(input_path).endswith('.jsonl')
        
        with open(input_path, 'r', encoding='utf-8') as f:
            if is_jsonl:
                # JSONL format - one JSON object per line
                rows_iter = _jsonl_reader(f)
            else:
                # CSV format
                sample = f.read(4096)
                f.seek(0)
                
                try:
                    dialect = csv.Sniffer().sniff(sample)
                except csv.Error:
                    dialect = csv.excel
                
                rows_iter = csv.DictReader(f, dialect=dialect)
            
            total_records = 0
            rows_processed = 0
            
            for i, row_dict in enumerate(rows_iter):
                # Use 'idx' field if present, otherwise use row number
                idx_val = row_dict.get('idx', row_dict.get('id', row_dict.get('ID', i)))
                try:
                    idx = int(idx_val)
                except (ValueError, TypeError):
                    logger.warning(f"Row {i}: Invalid idx value '{idx_val}', using row number")
                    idx = i
                
                # Filter by row_ids if specified
                if row_ids is not None and idx not in row_ids:
                    continue
                
                csv_row = CSVRow.from_dict(row_dict, idx)
                records = process_csv_row(csv_row)
                
                # Write records to appropriate files
                for record in records:
                    handle = handles.get(record.evidence_type)
                    if handle:
                        handle.write(json.dumps(record.to_dict()) + '\n')
                        total_records += 1
                
                rows_processed += 1
                
                if rows_processed % 100 == 0:
                    logger.info(f"Processed {rows_processed} rows, {total_records} evidence records")
    
    finally:
        for handle in handles.values():
            handle.close()
    
    logger.info(f"Ingestion complete: {rows_processed} rows → {total_records} evidence records")
    
    # Return only files that have content
    return {k: v for k, v in output_files.items() if v.exists() and v.stat().st_size > 0}


def _jsonl_reader(f) -> Iterator[dict]:
    """Read JSONL file line by line."""
    for line in f:
        line = line.strip()
        if line:
            try:
                yield json.loads(line)
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON line: {e}")
                continue


def ingest_single_row(row_dict: dict, idx: int) -> list[EvidenceRecord]:
    """
    Ingest a single row (for on-the-fly processing).
    """
    csv_row = CSVRow.from_dict(row_dict, idx)
    return process_csv_row(csv_row)


# =============================================================================
# ROW LOOKUP
# =============================================================================

def get_row_by_id(input_path: Path, row_id: int) -> dict | None:
    """
    Fetch a single row from CSV or JSONL file by its idx.
    """
    is_jsonl = str(input_path).endswith('.jsonl')
    
    with open(input_path, 'r', encoding='utf-8') as f:
        if is_jsonl:
            # JSONL format
            for i, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                    idx_val = row.get('idx', row.get('id', row.get('ID', i)))
                    try:
                        idx = int(idx_val)
                    except (ValueError, TypeError):
                        idx = i
                    if idx == row_id:
                        return row
                except json.JSONDecodeError:
                    continue
        else:
            # CSV format
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                idx = int(row.get('idx', row.get('id', row.get('ID', i))))
                if idx == row_id:
                    return row
    return None


# =============================================================================
# CLI ENTRYPOINT
# =============================================================================

def main() -> None:
    setup_logging(logging.INFO)
    
    parser = argparse.ArgumentParser(
        description="Ingest CSV into typed evidence records",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Evidence ID Format:
    CS_{idx}_{k}  - Summary JSON facts
    CN_{idx}_{k}  - Note chunks
    CF_{idx}_{k}  - Full note chunks
    CV_{idx}_{k}  - Conversation turns

Examples:
    python -m icu_copilot.ingest.ingest_csv --csv data.csv --out data/processed
    python -m icu_copilot.ingest.ingest_csv --csv data.csv --out data/processed --rows 1,5,10
        """
    )
    parser.add_argument("--csv", required=True, type=Path, help="Path to input CSV file")
    parser.add_argument("--out", required=True, type=Path, help="Output directory for JSONL files")
    parser.add_argument("--rows", type=str, help="Comma-separated row IDs to process (optional)")
    
    args = parser.parse_args()
    
    row_ids = None
    if args.rows:
        row_ids = [int(x.strip()) for x in args.rows.split(',')]
    
    if not args.csv.exists():
        logger.error(f"CSV file not found: {args.csv}")
        return
    
    output_files = ingest_csv_file(args.csv, args.out, row_ids)
    
    logger.info("=" * 50)
    logger.info("CSV INGESTION COMPLETE")
    logger.info("=" * 50)
    for etype, path in output_files.items():
        lines = sum(1 for _ in open(path, 'r', encoding='utf-8'))
        logger.info(f"  {etype:15s} → {path.name} ({lines} records)")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
