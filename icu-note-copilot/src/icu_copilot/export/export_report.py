"""Export report.json to printable Markdown and PDF formats."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def get_evidence_snippet(store: dict, eid: str, max_len: int = 150) -> str:
    """Get a truncated snippet from evidence store."""
    if eid not in store:
        return f"[{eid}] (not found)"
    
    rec = store[eid]
    raw_text = rec.get("raw_text", "")
    if len(raw_text) > max_len:
        raw_text = raw_text[:max_len] + "..."
    
    source = rec.get("source_file", "unknown")
    lines = f"L{rec.get('line_start', '?')}-{rec.get('line_end', '?')}"
    
    return f"[{eid}] ({source}:{lines}) {raw_text}"


def export_to_markdown(
    report_path: Path,
    evidence_store_path: Path,
    output_path: Optional[Path] = None,
) -> str:
    """
    Export report.json to a printable Markdown format.
    
    Returns the markdown string and optionally writes to output_path.
    """
    report = load_json(report_path)
    store = load_json(evidence_store_path)
    
    # Collect all evidence IDs used
    all_evidence_ids = set()
    
    lines = []
    
    # Header
    lines.append("# ICU Clinical Decision Support Report")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    lines.append("---")
    lines.append("")
    
    # === ICU SUMMARY ===
    lines.append("## 📋 ICU Summary")
    lines.append("")
    
    for bullet in report.get("summary", []):
        text = bullet.get("text", "")
        eids = bullet.get("evidence_ids", [])
        all_evidence_ids.update(eids)
        
        eid_str = ", ".join(eids) if eids else "—"
        lines.append(f"- **{text}** `[{eid_str}]`")
    
    lines.append("")
    lines.append("---")
    lines.append("")
    
    # === DIFFERENTIAL DIAGNOSIS ===
    lines.append("## 🔬 Differential Diagnosis (Ranked)")
    lines.append("")
    
    for i, dx in enumerate(report.get("differential", []), 1):
        diagnosis = dx.get("diagnosis", "Unknown")
        confidence = dx.get("confidence", "low")
        
        # Confidence badge
        conf_badge = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(confidence, "⚪")
        
        lines.append(f"### {i}. {diagnosis} {conf_badge} ({confidence.upper()})")
        lines.append("")
        
        # Support
        lines.append("**Supporting Evidence:**")
        for s in dx.get("support", []):
            eids = s.get("evidence_ids", [])
            all_evidence_ids.update(eids)
            eid_str = ", ".join(eids)
            lines.append(f"  - {s.get('label', '')}: {s.get('value', '')} `[{eid_str}]`")
        
        # Against
        against = dx.get("against", [])
        if against and against[0].get("label") != "No documented contradictory evidence":
            lines.append("")
            lines.append("**Against:**")
            for a in against:
                eids = a.get("evidence_ids", [])
                all_evidence_ids.update(eids)
                eid_str = ", ".join(eids) if eids else "—"
                lines.append(f"  - {a.get('label', '')}: {a.get('value', '')} `[{eid_str}]`")
        
        # Missing
        missing = dx.get("missing", [])
        if missing:
            lines.append("")
            lines.append("**Missing (to confirm/rule out):**")
            for m in missing:
                lines.append(f"  - ❓ {m}")
        
        lines.append("")
    
    lines.append("---")
    lines.append("")
    
    # === CLARIFYING QUESTIONS ===
    lines.append("## ❓ Clarifying Questions")
    lines.append("")
    
    questions = report.get("clarifying_questions", [])
    if questions:
        # Sort by priority
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        questions_sorted = sorted(questions, key=lambda q: priority_order.get(q.get("priority", "low"), 3))
        
        for q in questions_sorted:
            priority = q.get("priority", "medium")
            priority_badge = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(priority, "⚪")
            
            eids = q.get("evidence_ids", [])
            all_evidence_ids.update(eids)
            eid_str = ", ".join(set(eids)) if eids else "—"
            
            lines.append(f"- {priority_badge} **[{priority.upper()}]** {q.get('question', '')}")
            lines.append(f"  - *Rationale:* {q.get('rationale', '')} `[{eid_str}]`")
            lines.append("")
    else:
        lines.append("*No clarifying questions generated.*")
        lines.append("")
    
    lines.append("---")
    lines.append("")
    
    # === ACTION ITEMS ===
    lines.append("## ✅ Action Items")
    lines.append("")
    
    actions = report.get("action_items", [])
    if actions:
        for a in actions:
            priority = a.get("priority", "medium")
            priority_badge = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(priority, "⚪")
            
            eids = a.get("evidence_ids", [])
            all_evidence_ids.update(eids)
            eid_str = ", ".join(eids) if eids else "—"
            
            lines.append(f"- {priority_badge} **[{priority.upper()}]** {a.get('item', '')}")
            lines.append(f"  - *Rationale:* {a.get('rationale', '')} `[{eid_str}]`")
            lines.append("")
    else:
        lines.append("*No action items generated.*")
        lines.append("")
    
    lines.append("---")
    lines.append("")
    
    # === LIMITATIONS ===
    lines.append("## ⚠️ Limitations")
    lines.append("")
    
    limitations = report.get("limitations", [])
    if limitations:
        for lim in limitations:
            lines.append(f"- {lim}")
    else:
        lines.append("- Limited to evidence available in patient record")
        lines.append("- No medication data extracted")
        lines.append("- Monitor data may be incomplete")
    
    lines.append("")
    lines.append("---")
    lines.append("")
    
    # === EVIDENCE APPENDIX ===
    lines.append("## 📎 Evidence Appendix")
    lines.append("")
    lines.append("*All cited evidence IDs with source snippets:*")
    lines.append("")
    
    # Sort evidence IDs
    sorted_eids = sorted(all_evidence_ids, key=lambda x: (x[0], int(x[1:]) if x[1:].isdigit() else 0))
    
    for eid in sorted_eids:
        snippet = get_evidence_snippet(store, eid, max_len=200)
        lines.append(f"- {snippet}")
    
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*This report is for clinical decision support only. All findings require physician review.*")
    
    md_content = "\n".join(lines)
    
    if output_path:
        output_path.write_text(md_content, encoding="utf-8")
        logger.info(f"Markdown report exported to: {output_path}")
    
    return md_content


def export_to_pdf(
    markdown_path: Path,
    output_path: Path,
) -> bool:
    """
    Export Markdown to PDF using markdown2 + weasyprint or reportlab.
    Returns True if successful.
    """
    try:
        import markdown2
        from weasyprint import HTML, CSS
        
        md_content = markdown_path.read_text(encoding="utf-8")
        html_content = markdown2.markdown(md_content, extras=["fenced-code-blocks", "tables"])
        
        # Add basic styling
        styled_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    font-size: 11pt;
                    line-height: 1.4;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                h1 {{ color: #1a5f7a; border-bottom: 2px solid #1a5f7a; padding-bottom: 10px; }}
                h2 {{ color: #2d3436; margin-top: 25px; }}
                h3 {{ color: #636e72; }}
                code {{ background: #f1f2f6; padding: 2px 6px; border-radius: 3px; font-size: 10pt; }}
                ul {{ margin-left: 20px; }}
                li {{ margin-bottom: 8px; }}
                hr {{ border: none; border-top: 1px solid #ddd; margin: 20px 0; }}
            </style>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """
        
        HTML(string=styled_html).write_pdf(str(output_path))
        logger.info(f"PDF report exported to: {output_path}")
        return True
        
    except ImportError as e:
        logger.warning(f"PDF export requires 'markdown2' and 'weasyprint': {e}")
        logger.info("Install with: pip install markdown2 weasyprint")
        return False
    except Exception as e:
        logger.error(f"PDF export failed: {e}")
        return False


def main():
    logging.basicConfig(level=logging.INFO)
    
    root = Path(__file__).resolve().parents[4]
    run_dir = root / "data" / "processed" / "runs" / "latest"
    indices_dir = root / "data" / "indices"
    
    report_path = run_dir / "report.json"
    evidence_store_path = indices_dir / "evidence_store.json"
    
    if not report_path.exists():
        logger.error(f"Report not found: {report_path}")
        return
    
    # Export to Markdown
    md_path = run_dir / "report.md"
    export_to_markdown(report_path, evidence_store_path, md_path)
    
    # Try to export to PDF
    pdf_path = run_dir / "report.pdf"
    export_to_pdf(md_path, pdf_path)
    
    logger.info("Export complete!")


if __name__ == "__main__":
    main()
