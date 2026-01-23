"""Streamlit Explainability UI for ICU Copilot."""
from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

# Page config
st.set_page_config(
    page_title="ICU Copilot",
    page_icon="🏥",
    layout="wide",
)

# Paths
ROOT = Path(__file__).resolve().parents[4]
DATA_DIR = ROOT / "data"
INDICES_DIR = DATA_DIR / "indices"
RUNS_DIR = DATA_DIR / "processed" / "runs" / "latest"


@st.cache_data
def load_json(path: Path) -> dict:
    """Load JSON file."""
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


@st.cache_data
def load_evidence_store() -> dict:
    """Load evidence store."""
    return load_json(INDICES_DIR / "evidence_store.json")


def render_evidence_popup(evidence_id: str, store: dict):
    """Render evidence details in sidebar."""
    if evidence_id not in store:
        st.sidebar.error(f"Evidence not found: {evidence_id}")
        return
    
    record = store[evidence_id]
    
    st.sidebar.markdown(f"### 📎 {evidence_id}")
    st.sidebar.markdown(f"**Type:** {record.get('evidence_type', 'unknown')}")
    st.sidebar.markdown(f"**Source:** `{record.get('source_file', 'unknown')}`")
    st.sidebar.markdown(f"**Lines:** {record.get('line_start', '?')} - {record.get('line_end', '?')}")
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Raw Text:**")
    st.sidebar.code(record.get("raw_text", ""), language=None)


def main():
    # Load data
    report = load_json(RUNS_DIR / "report.json")
    quality = load_json(RUNS_DIR / "quality_gate.json")
    store = load_evidence_store()
    
    if not report:
        st.error("❌ No report found. Please run the pipeline first.")
        st.code("python -m icu_copilot.pipeline.run_llm")
        return
    
    # Header
    st.title("🏥 ICU Clinical Decision Support")
    st.markdown("*AI-assisted patient summarization with full evidence traceability*")
    
    # Quality metrics
    if quality:
        col1, col2, col3 = st.columns(3)
        with col1:
            score = quality.get("score", 0)
            status = "✅ PASS" if quality.get("passed", False) else "❌ FAIL"
            st.metric("Quality Score", f"{score}/100", status)
        with col2:
            metrics = quality.get("metrics", {})
            st.metric("Differential Count", metrics.get("differential", {}).get("differential_count", 0))
        with col3:
            st.metric("Summary Bullets", metrics.get("summary", {}).get("total_bullets", 0))
    
    st.markdown("---")
    
    # Two-column layout
    left_col, right_col = st.columns([2, 1])
    
    # === LEFT COLUMN: Report Sections ===
    with left_col:
        # ICU Summary (from patient_state)
        st.header("📋 ICU Summary")
        
        patient_state = report.get("patient_state", {})
        
        # Diagnoses
        diagnoses = patient_state.get("diagnoses", [])
        if diagnoses:
            st.markdown("**Diagnoses:**")
            for dx in diagnoses:
                label = dx.get("label", "")
                eids = dx.get("evidence_ids", [])
                eid_buttons = " ".join([f"`{eid}`" for eid in eids])
                st.markdown(f"• {label} {eid_buttons}")
                for eid in eids:
                    if st.button(f"📎 {eid}", key=f"dx_{eid}_{label[:15]}", help=f"View evidence {eid}"):
                        st.session_state["selected_evidence"] = eid
        
        # Procedures
        procedures = patient_state.get("procedures", [])
        if procedures:
            st.markdown("**Procedures/History:**")
            for proc in procedures:
                label = proc.get("label", "")
                eids = proc.get("evidence_ids", [])
                eid_buttons = " ".join([f"`{eid}`" for eid in eids])
                st.markdown(f"• {label} {eid_buttons}")
                for eid in eids:
                    if st.button(f"📎 {eid}", key=f"proc_{eid}_{label[:15]}", help=f"View evidence {eid}"):
                        st.session_state["selected_evidence"] = eid
        
        # Key Labs (from timeline)
        timeline = patient_state.get("timeline", [])
        if timeline:
            st.markdown("**Key Labs:**")
            for lab in timeline[:8]:  # Limit to first 8
                label = lab.get("label", "")
                value = lab.get("value", "")
                eids = lab.get("evidence_ids", [])
                eid_buttons = " ".join([f"`{eid}`" for eid in eids])
                st.markdown(f"• {label} = {value} {eid_buttons}")
                for eid in eids:
                    if st.button(f"📎 {eid}", key=f"lab_{eid}_{label}_{value}", help=f"View evidence {eid}"):
                        st.session_state["selected_evidence"] = eid
        
        st.markdown("---")
        
        # Differential Diagnosis
        st.header("🔬 Differential Diagnosis")
        
        for i, dx in enumerate(report.get("differential", []), 1):
            confidence = dx.get("confidence", "low")
            conf_color = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(confidence, "⚪")
            
            with st.expander(f"{conf_color} **{i}. {dx.get('diagnosis', '')}** ({confidence})", expanded=(i <= 2)):
                # Support
                st.markdown("**Supporting Evidence:**")
                for s in dx.get("support", []):
                    eids = s.get("evidence_ids", [])
                    eid_str = ", ".join(eids)
                    st.markdown(f"  - {s.get('label', '')}: {s.get('value', '')} `[{eid_str}]`")
                    
                    for eid in eids:
                        if st.button(f"View {eid}", key=f"dx_{i}_{eid}"):
                            st.session_state["selected_evidence"] = eid
                
                # Missing
                missing = dx.get("missing", [])
                if missing:
                    st.markdown("**Missing (to confirm):**")
                    for m in missing:
                        st.markdown(f"  - ❓ {m}")
        
        st.markdown("---")
        
        # Clarifying Questions
        st.header("❓ Clarifying Questions")
        
        questions = report.get("clarifying_questions", [])
        if questions:
            for q in questions:
                priority = q.get("priority", "medium")
                priority_badge = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(priority, "⚪")
                
                st.markdown(f"{priority_badge} **[{priority.upper()}]** {q.get('question', '')}")
                st.markdown(f"  *{q.get('rationale', '')}*")
                
                eids = q.get("evidence_ids", [])
                for eid in set(eids):
                    if st.button(f"📎 {eid}", key=f"q_{eid}_{q.get('question', '')[:20]}"):
                        st.session_state["selected_evidence"] = eid
        else:
            st.info("No clarifying questions generated.")
        
        st.markdown("---")
        
        # Action Items
        st.header("✅ Action Items")
        
        actions = report.get("action_items", [])
        if actions:
            for a in actions:
                priority = a.get("priority", "medium")
                priority_badge = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(priority, "⚪")
                
                st.markdown(f"{priority_badge} **[{priority.upper()}]** {a.get('item', '')}")
                st.markdown(f"  *{a.get('rationale', '')}*")
        else:
            st.info("No action items generated.")
    
    # === RIGHT COLUMN: Evidence Viewer ===
    with right_col:
        st.header("📎 Evidence Viewer")
        
        # Evidence ID input
        selected = st.text_input(
            "Enter Evidence ID:",
            value=st.session_state.get("selected_evidence", ""),
            placeholder="e.g., N000001, L000040",
        )
        
        if selected:
            st.session_state["selected_evidence"] = selected
            
            if selected in store:
                record = store[selected]
                
                st.markdown(f"### {selected}")
                
                st.markdown(f"**Type:** `{record.get('evidence_type', 'unknown')}`")
                st.markdown(f"**Source:** `{record.get('source_file', 'unknown')}`")
                st.markdown(f"**Lines:** {record.get('line_start', '?')} - {record.get('line_end', '?')}")
                
                st.markdown("---")
                st.markdown("**Raw Text:**")
                st.code(record.get("raw_text", ""), language=None)
            else:
                st.error(f"Evidence ID not found: {selected}")
        
        st.markdown("---")
        
        # Quick access to common evidence types
        st.markdown("### Quick Access")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("📝 Narrative (N)"):
                st.session_state["filter_prefix"] = "N"
        with col2:
            if st.button("🧪 Labs (L)"):
                st.session_state["filter_prefix"] = "L"
        with col3:
            if st.button("📊 Monitor (M)"):
                st.session_state["filter_prefix"] = "M"
        
        # Show filtered evidence list
        filter_prefix = st.session_state.get("filter_prefix", "")
        if filter_prefix:
            st.markdown(f"**{filter_prefix} Evidence:**")
            filtered = [eid for eid in store.keys() if eid.startswith(filter_prefix)][:10]
            
            for eid in filtered:
                preview = store[eid].get("raw_text", "")[:50]
                if st.button(f"{eid}: {preview}...", key=f"list_{eid}"):
                    st.session_state["selected_evidence"] = eid


if __name__ == "__main__":
    main()
