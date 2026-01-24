#!/usr/bin/env python3
"""
Download and export the augmented-clinical-notes dataset to CSV.

Usage:
    python download_dataset.py                    # Export all 30K rows
    python download_dataset.py --limit 100        # Export first 100 rows
    python download_dataset.py --rows 155216,1234 # Export specific rows by idx
"""
import argparse
import csv
import json
from pathlib import Path

from datasets import load_dataset

def main():
    parser = argparse.ArgumentParser(description="Download and export clinical notes dataset")
    parser.add_argument("--limit", type=int, help="Limit number of rows to export")
    parser.add_argument("--rows", type=str, help="Comma-separated list of idx values to export")
    parser.add_argument("--out", type=Path, default=Path("data/clinical_notes.csv"), help="Output CSV path")
    parser.add_argument("--explore", action="store_true", help="Just explore dataset structure")
    parser.add_argument("--jsonl", action="store_true", help="Export as JSONL instead of CSV (safer for nested JSON)")
    args = parser.parse_args()

    print("Loading dataset from HuggingFace...")
    ds = load_dataset("AGBonnet/augmented-clinical-notes")
    
    split = list(ds.keys())[0]
    data = ds[split]
    
    print(f"Dataset loaded: {len(data)} rows")
    print(f"Columns: {data.column_names}")
    
    if args.explore:
        print("\n" + "="*60)
        print("SAMPLE ROW:")
        print("="*60)
        row = data[0]
        for k, v in row.items():
            val_str = str(v)[:500] + "..." if len(str(v)) > 500 else str(v)
            print(f"\n=== {k} ===")
            print(val_str)
        return
    
    # Filter rows if specified
    if args.rows:
        target_ids = set(int(x.strip()) for x in args.rows.split(","))
        indices = [i for i, row in enumerate(data) if row["idx"] in target_ids]
        print(f"Filtering to {len(indices)} specific rows")
    elif args.limit:
        indices = list(range(min(args.limit, len(data))))
        print(f"Limiting to first {len(indices)} rows")
    else:
        indices = list(range(len(data)))
    
    args.out.parent.mkdir(parents=True, exist_ok=True)
    
    # Map column names (summary -> summary_json for our pipeline)
    column_map = {
        "idx": "idx",
        "note": "note",
        "full_note": "full_note",
        "conversation": "conversation",
        "summary": "summary_json",  # Rename for our pipeline
    }
    
    if args.jsonl:
        # Export as JSONL (safer for nested JSON)
        out_path = args.out.with_suffix(".jsonl")
        with open(out_path, "w", encoding="utf-8") as f:
            for i in indices:
                row = data[i]
                out_row = {column_map[k]: v for k, v in row.items()}
                f.write(json.dumps(out_row, ensure_ascii=False) + "\n")
        print(f"\n✅ Exported {len(indices)} rows to: {out_path}")
    else:
        # Export to CSV with proper quoting
        with open(args.out, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f, 
                fieldnames=list(column_map.values()),
                quoting=csv.QUOTE_ALL,  # Quote all fields to handle embedded JSON
                escapechar="\\",
            )
            writer.writeheader()
            
            for i in indices:
                row = data[i]
                out_row = {column_map[k]: v for k, v in row.items()}
                writer.writerow(out_row)
        
        print(f"\n✅ Exported {len(indices)} rows to: {args.out}")
    
    print(f"   Columns: {list(column_map.values())}")


if __name__ == "__main__":
    main()
