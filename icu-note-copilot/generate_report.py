#!/usr/bin/env python3
"""
Generate Clinical Report

Supports multiple modes:
1. Q&A Summary (legacy ICU data)
2. SOAP Case Report (CSV data with row_id)
3. CSV Ingestion

Usage:
    python generate_report.py                     # Q&A summary (legacy)
    python generate_report.py --csv data.csv --row 123  # SOAP case report
    python generate_report.py --ingest data.csv  # Ingest CSV to JSONL
"""
import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

ROOT = Path(__file__).parent
RUNS_DIR = ROOT / "data/processed/runs/latest"


def run_qa_summary():
    """Run the Q&A summarization pipeline."""
    from icu_copilot.pipeline.run_qa_summary import main as qa_main
    qa_main()


def run_case_pipeline(csv_path: Path | None, row_id: int, output_dir: Path | None):
    """Run SOAP case pipeline for a single row."""
    from icu_copilot.pipeline.run_case import CasePipeline
    
    indices_dir = ROOT / "data" / "indices"
    out_dir = output_dir or (ROOT / "data" / "processed" / "runs")
    
    pipeline = CasePipeline(
        indices_dir=indices_dir,
        csv_path=csv_path,
    )
    
    report = pipeline.run(row_id)
    
    # Save outputs
    case_dir = out_dir / f"case_{row_id}"
    case_dir.mkdir(parents=True, exist_ok=True)
    
    # JSON output
    json_path = case_dir / "report.json"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    
    # Text output
    text_output = pipeline.format_text_output(report)
    text_path = case_dir / "report.txt"
    text_path.write_text(text_output, encoding="utf-8")
    
    print(text_output)
    print(f"\n✅ Case report saved to: {case_dir}")
    
    return report


def run_batch_pipeline(csv_path: Path | None, row_ids: list[int], output_dir: Path | None):
    """Run SOAP case pipeline for multiple rows."""
    import time
    from icu_copilot.pipeline.run_case import CasePipeline
    
    indices_dir = ROOT / "data" / "indices"
    out_dir = output_dir or (ROOT / "data" / "processed" / "runs")
    batch_dir = out_dir / "batch_output"
    batch_dir.mkdir(parents=True, exist_ok=True)
    
    pipeline = CasePipeline(
        indices_dir=indices_dir,
        csv_path=csv_path,
    )
    
    all_reports = []
    start_time = time.time()
    
    for i, row_id in enumerate(row_ids, 1):
        case_start = time.time()
        print(f"\n{'='*60}")
        print(f"Processing case {i}/{len(row_ids)}: Row {row_id}")
        print(f"{'='*60}")
        
        try:
            report = pipeline.run(row_id)
            all_reports.append(report)
            
            # Save individual case
            case_dir = batch_dir / f"case_{row_id}"
            case_dir.mkdir(parents=True, exist_ok=True)
            
            json_path = case_dir / "report.json"
            json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
            
            text_output = pipeline.format_text_output(report)
            text_path = case_dir / "report.txt"
            text_path.write_text(text_output, encoding="utf-8")
            
            case_time = time.time() - case_start
            print(f"✅ Case {row_id} complete in {case_time:.1f}s")
            
        except Exception as e:
            print(f"❌ Case {row_id} failed: {e}")
            continue
    
    total_time = time.time() - start_time
    
    # Generate combined summary
    summary_lines = [
        "=" * 80,
        "BATCH PROCESSING SUMMARY",
        f"Total cases: {len(all_reports)}/{len(row_ids)}",
        f"Total time: {total_time:.1f}s ({total_time/len(row_ids):.1f}s per case)",
        "=" * 80,
        ""
    ]
    
    for report in all_reports:
        summary_lines.append(f"### Case {report.row_id}")
        summary_lines.append(report.soap_summary[:500] + "..." if len(report.soap_summary) > 500 else report.soap_summary)
        summary_lines.append(f"Differentials: {[d['diagnosis'] for d in report.differential]}")
        summary_lines.append("")
    
    summary_text = "\n".join(summary_lines)
    summary_path = batch_dir / "batch_summary.txt"
    summary_path.write_text(summary_text, encoding="utf-8")
    
    print(f"\n{'='*60}")
    print(f"BATCH COMPLETE: {len(all_reports)} cases in {total_time:.1f}s")
    print(f"Output: {batch_dir}")
    print(f"{'='*60}")


def run_csv_ingestion(csv_path: Path, output_dir: Path | None):
    """Ingest CSV file into typed evidence records."""
    from icu_copilot.ingest.ingest_csv import ingest_csv_file
    
    out_dir = output_dir or (ROOT / "data" / "processed")
    output_files = ingest_csv_file(csv_path, out_dir)
    
    print("\n✅ CSV Ingestion Complete:")
    for etype, path in output_files.items():
        lines = sum(1 for _ in open(path, 'r', encoding='utf-8'))
        print(f"   {etype:15s} → {path.name} ({lines} records)")


def run_markdown_export():
    """Export to markdown (legacy format)."""
    from icu_copilot.export.export_report import export_to_markdown
    
    REPORT_PATH = RUNS_DIR / "report.json"
    EVIDENCE_STORE = ROOT / "data/indices/evidence_store.json"
    OUTPUT_PATH = RUNS_DIR / "report.md"
    
    output = export_to_markdown(REPORT_PATH, EVIDENCE_STORE, OUTPUT_PATH)
    print(f"✅ Markdown exported to: {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate Clinical Reports (Q&A or SOAP format)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modes:
  Legacy Q&A:   python generate_report.py
  SOAP Case:    python generate_report.py --csv data.csv --row 123
  CSV Ingest:   python generate_report.py --ingest data.csv

Examples:
    python generate_report.py                          # Q&A from indexed ICU data
    python generate_report.py --csv cases.csv --row 5  # SOAP report for row 5
    python generate_report.py --csv cases.csv --rows 5,10,15  # Batch process multiple rows
    python generate_report.py --csv cases.csv --first 5       # Process first 5 rows
    python generate_report.py --ingest cases.csv      # Ingest CSV → JSONL
    python generate_report.py --rebuild-index         # Rebuild search index

Output Files:
    Q&A Mode:    data/processed/runs/latest/qa_summary.txt
    SOAP Mode:   data/processed/runs/case_{row}/report.txt
    Batch Mode:  data/processed/runs/batch_output/
    Ingest:      data/processed/csv_*.jsonl
        """
    )
    
    # Mode selection
    parser.add_argument("--csv", type=Path, help="Path to CSV file for case processing")
    parser.add_argument("--row", type=int, help="Row ID to process (requires --csv or indexed data)")
    parser.add_argument("--rows", type=str, help="Comma-separated row IDs for batch processing")
    parser.add_argument("--first", type=int, metavar="N", help="Process first N rows from CSV")
    parser.add_argument("--ingest", type=Path, metavar="CSV", help="Ingest CSV file into evidence records")
    parser.add_argument("--rebuild-index", action="store_true", help="Rebuild search indices after ingestion")
    
    # Options
    parser.add_argument("--out", type=Path, help="Output directory")
    parser.add_argument("--markdown", action="store_true", help="Also export legacy markdown report")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("🏥 CLINICAL REPORT GENERATOR")
    print("=" * 60)
    print()
    
    try:
        # Mode: CSV Ingestion
        if args.ingest:
            print(f"Mode: CSV Ingestion")
            print(f"Input: {args.ingest}")
            print("-" * 60)
            run_csv_ingestion(args.ingest, args.out)
            
            if args.rebuild_index:
                print("\n" + "-" * 60)
                print("Rebuilding search indices...")
                from icu_copilot.rag.index_build import build_and_save_indices
                processed_dir = args.out or (ROOT / "data" / "processed")
                indices_dir = ROOT / "data" / "indices"
                build_and_save_indices(processed_dir, indices_dir)
                print("✅ Index rebuild complete")
        
        # Mode: SOAP Case Report (single row)
        elif args.row is not None:
            print(f"Mode: SOAP Case Report")
            print(f"Row ID: {args.row}")
            if args.csv:
                print(f"CSV: {args.csv}")
            print("-" * 60)
            run_case_pipeline(args.csv, args.row, args.out)
        
        # Mode: Batch Processing (multiple rows)
        elif args.rows or args.first:
            if not args.csv:
                print("❌ Error: --csv is required for batch processing")
                sys.exit(1)
            
            # Get row IDs
            if args.rows:
                row_ids = [int(x.strip()) for x in args.rows.split(',')]
                print(f"Mode: Batch Processing")
                print(f"Rows: {row_ids}")
            else:
                # Get first N row IDs from file
                import json
                is_jsonl = str(args.csv).endswith('.jsonl')
                row_ids = []
                with open(args.csv, 'r', encoding='utf-8') as f:
                    if is_jsonl:
                        for i, line in enumerate(f):
                            if i >= args.first:
                                break
                            try:
                                data = json.loads(line.strip())
                                row_ids.append(int(data.get('idx', i)))
                            except:
                                continue
                    else:
                        import csv
                        reader = csv.DictReader(f)
                        for i, row in enumerate(reader):
                            if i >= args.first:
                                break
                            row_ids.append(int(row.get('idx', i)))
                
                print(f"Mode: Batch Processing (first {args.first} rows)")
                print(f"Rows: {row_ids}")
            
            print(f"CSV: {args.csv}")
            print("-" * 60)
            run_batch_pipeline(args.csv, row_ids, args.out)
        
        # Mode: Legacy Q&A Summary
        else:
            print("Mode: Q&A Summary (legacy ICU data)")
            print("-" * 60)
            run_qa_summary()
            
            if args.markdown:
                print("\n" + "-" * 60)
                run_markdown_export()
        
        print()
        print("=" * 60)
        print("✅ Report generation complete!")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
