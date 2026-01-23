"""
ICU Clinical Decision Support - Professional Web Interface
A clinical-themed, interactive webapp for displaying patient analysis.
"""
from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime

import streamlit as st

# ═══════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="ICU Clinical Decision Support",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Paths
ROOT = Path(__file__).resolve().parents[3]  # icu-note-copilot/
DATA_DIR = ROOT / "data"
INDICES_DIR = DATA_DIR / "indices"
RUNS_DIR = DATA_DIR / "processed" / "runs" / "latest"

# ═══════════════════════════════════════════════════════════════════
# Clinical Theme CSS
# ═══════════════════════════════════════════════════════════════════

CLINICAL_CSS = """
<style>
    /* Import Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    /* Global Styles */
    .stApp {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    /* Header Banner */
    .clinical-header {
        background: linear-gradient(135deg, #1a365d 0%, #2c5282 50%, #2b6cb0 100%);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 15px rgba(26, 54, 93, 0.3);
    }
    
    .clinical-header h1 {
        color: white;
        margin: 0;
        font-weight: 600;
        font-size: 1.8rem;
        letter-spacing: -0.5px;
    }
    
    .clinical-header p {
        color: #bee3f8;
        margin: 0.5rem 0 0 0;
        font-size: 0.95rem;
    }
    
    /* Stage Pipeline */
    .pipeline-container {
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: #f7fafc;
        padding: 1rem 1.5rem;
        border-radius: 10px;
        margin-bottom: 1.5rem;
        border: 1px solid #e2e8f0;
    }
    
    .pipeline-stage {
        display: flex;
        flex-direction: column;
        align-items: center;
        padding: 0.5rem 1rem;
        border-radius: 8px;
        transition: all 0.2s;
        cursor: pointer;
    }
    
    .pipeline-stage.active {
        background: #2c5282;
        color: white;
    }
    
    .pipeline-stage.completed {
        background: #48bb78;
        color: white;
    }
    
    .pipeline-arrow {
        color: #a0aec0;
        font-size: 1.5rem;
    }
    
    /* Cards */
    .clinical-card {
        background: white;
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        border: 1px solid #e2e8f0;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
    }
    
    .clinical-card-header {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        margin-bottom: 1rem;
        padding-bottom: 0.75rem;
        border-bottom: 2px solid #e2e8f0;
    }
    
    .clinical-card-header h3 {
        margin: 0;
        color: #1a365d;
        font-weight: 600;
        font-size: 1.1rem;
    }
    
    .clinical-card-icon {
        font-size: 1.3rem;
    }
    
    /* Patient Banner */
    .patient-banner {
        background: linear-gradient(90deg, #ebf8ff 0%, #ffffff 100%);
        border-left: 4px solid #3182ce;
        padding: 1rem 1.25rem;
        border-radius: 0 8px 8px 0;
        margin-bottom: 1.5rem;
    }
    
    .patient-banner h2 {
        color: #2c5282;
        margin: 0;
        font-size: 1.1rem;
        font-weight: 600;
    }
    
    .patient-banner p {
        color: #4a5568;
        margin: 0.25rem 0 0 0;
        font-size: 0.9rem;
    }
    
    /* Diagnosis Cards */
    .dx-card {
        background: white;
        border-radius: 10px;
        padding: 1.25rem;
        margin-bottom: 0.75rem;
        border: 1px solid #e2e8f0;
        transition: all 0.2s;
    }
    
    .dx-card:hover {
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
        border-color: #cbd5e0;
    }
    
    .dx-card.high {
        border-left: 4px solid #48bb78;
    }
    
    .dx-card.medium {
        border-left: 4px solid #ecc94b;
    }
    
    .dx-card.low {
        border-left: 4px solid #fc8181;
    }
    
    .dx-title {
        font-weight: 600;
        color: #1a365d;
        font-size: 1rem;
        margin-bottom: 0.5rem;
    }
    
    .confidence-badge {
        display: inline-block;
        padding: 0.2rem 0.6rem;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    .confidence-high {
        background: #c6f6d5;
        color: #22543d;
    }
    
    .confidence-medium {
        background: #fefcbf;
        color: #744210;
    }
    
    .confidence-low {
        background: #fed7d7;
        color: #742a2a;
    }
    
    /* Evidence Badge */
    .evidence-badge {
        display: inline-block;
        background: #edf2f7;
        color: #4a5568;
        padding: 0.15rem 0.5rem;
        border-radius: 4px;
        font-size: 0.75rem;
        font-family: 'SF Mono', 'Monaco', monospace;
        margin: 0.1rem;
        cursor: pointer;
        transition: all 0.15s;
        border: 1px solid transparent;
    }
    
    .evidence-badge:hover {
        background: #3182ce;
        color: white;
        border-color: #2c5282;
    }
    
    /* Question/Action Items */
    .action-item {
        display: flex;
        align-items: flex-start;
        gap: 0.75rem;
        padding: 0.75rem 1rem;
        background: #f7fafc;
        border-radius: 8px;
        margin-bottom: 0.5rem;
        border: 1px solid #e2e8f0;
    }
    
    .action-item.critical {
        background: #fff5f5;
        border-color: #feb2b2;
    }
    
    .action-item.high {
        background: #fffaf0;
        border-color: #fbd38d;
    }
    
    .priority-dot {
        width: 10px;
        height: 10px;
        border-radius: 50%;
        margin-top: 0.35rem;
        flex-shrink: 0;
    }
    
    .priority-critical { background: #e53e3e; }
    .priority-high { background: #ed8936; }
    .priority-medium { background: #ecc94b; }
    .priority-low { background: #48bb78; }
    
    /* Evidence Viewer */
    .evidence-viewer {
        background: #1a365d;
        border-radius: 10px;
        padding: 1.25rem;
        color: white;
    }
    
    .evidence-viewer-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 1rem;
        padding-bottom: 0.75rem;
        border-bottom: 1px solid #2c5282;
    }
    
    .evidence-viewer h4 {
        margin: 0;
        font-weight: 600;
    }
    
    .evidence-meta {
        display: flex;
        gap: 1rem;
        margin-bottom: 0.75rem;
        font-size: 0.85rem;
        color: #a0aec0;
    }
    
    .evidence-content {
        background: #2d3748;
        padding: 1rem;
        border-radius: 6px;
        font-family: 'SF Mono', 'Monaco', monospace;
        font-size: 0.85rem;
        line-height: 1.6;
        white-space: pre-wrap;
        color: #e2e8f0;
    }
    
    /* Quality Score */
    .quality-score {
        display: flex;
        align-items: center;
        gap: 1rem;
        padding: 1rem;
        background: linear-gradient(90deg, #f0fff4 0%, #ffffff 100%);
        border-radius: 10px;
        border: 1px solid #9ae6b4;
    }
    
    .score-circle {
        width: 60px;
        height: 60px;
        border-radius: 50%;
        background: linear-gradient(135deg, #48bb78 0%, #38a169 100%);
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-size: 1.5rem;
        font-weight: 700;
        box-shadow: 0 4px 10px rgba(72, 187, 120, 0.3);
    }
    
    /* Sidebar Styles */
    .sidebar-section {
        background: #f7fafc;
        padding: 1rem;
        border-radius: 8px;
        margin-bottom: 1rem;
    }
    
    .sidebar-section h4 {
        margin: 0 0 0.75rem 0;
        color: #2d3748;
        font-size: 0.9rem;
        font-weight: 600;
    }
    
    /* Tab Styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background: #f7fafc;
        padding: 0.5rem;
        border-radius: 10px;
    }
    
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        padding: 0.5rem 1rem;
        font-weight: 500;
    }
    
    .stTabs [aria-selected="true"] {
        background: #2c5282 !important;
        color: white !important;
    }
    
    /* Expander */
    .streamlit-expanderHeader {
        background: #f7fafc;
        border-radius: 8px;
        font-weight: 500;
    }
    
    /* Hide Streamlit Elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Scrollbar */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    
    ::-webkit-scrollbar-track {
        background: #f1f1f1;
        border-radius: 4px;
    }
    
    ::-webkit-scrollbar-thumb {
        background: #cbd5e0;
        border-radius: 4px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: #a0aec0;
    }
</style>
"""

# ═══════════════════════════════════════════════════════════════════
# Data Loading
# ═══════════════════════════════════════════════════════════════════

@st.cache_data
def load_json_file(path: Path) -> dict:
    """Load JSON file with caching."""
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


@st.cache_data
def load_all_data():
    """Load all required data files."""
    return {
        "report": load_json_file(RUNS_DIR / "report.json"),
        "quality": load_json_file(RUNS_DIR / "quality_gate.json"),
        "summary": load_json_file(RUNS_DIR / "summary.json"),
        "differential": load_json_file(RUNS_DIR / "differential.json"),
        "patient_state": load_json_file(RUNS_DIR / "patient_state.json"),
        "evidence_store": load_json_file(INDICES_DIR / "evidence_store.json"),
    }


# ═══════════════════════════════════════════════════════════════════
# UI Components
# ═══════════════════════════════════════════════════════════════════

def render_header():
    """Render the clinical header banner."""
    st.markdown(CLINICAL_CSS, unsafe_allow_html=True)
    st.markdown("""
    <div class="clinical-header">
        <h1>🏥 ICU Clinical Decision Support</h1>
        <p>AI-Assisted Patient Analysis with Evidence Traceability</p>
    </div>
    """, unsafe_allow_html=True)


def render_patient_banner(data: dict):
    """Render patient information banner."""
    patient_state = data.get("report", {}).get("patient_state", {})
    
    # Extract patient info from narrative
    demographics = patient_state.get("demographics", [])
    demo_text = demographics[0].get("value", "ICU Patient") if demographics else "ICU Patient"
    
    diagnoses = patient_state.get("diagnoses", [])
    primary_dx = ", ".join([d.get("label", "") for d in diagnoses[:3]]) if diagnoses else "Under evaluation"
    
    st.markdown(f"""
    <div class="patient-banner">
        <h2>📋 {demo_text}</h2>
        <p><strong>Primary Problems:</strong> {primary_dx}</p>
    </div>
    """, unsafe_allow_html=True)


def render_quality_metrics(data: dict):
    """Render quality score and metrics."""
    quality = data.get("quality", {})
    if not quality:
        return
    
    score = quality.get("score", 0)
    passed = quality.get("passed", False)
    metrics = quality.get("metrics", {})
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Quality Score",
            f"{score}/100",
            "PASS ✓" if passed else "REVIEW",
        )
    
    with col2:
        diff_count = metrics.get("differential", {}).get("differential_count", 0)
        st.metric("Diagnoses", diff_count)
    
    with col3:
        bullets = metrics.get("summary", {}).get("total_bullets", 0)
        st.metric("Summary Items", bullets)
    
    with col4:
        organs = metrics.get("summary", {}).get("organ_systems_covered", 0)
        st.metric("Organ Systems", organs)


def render_pipeline_nav():
    """Render the pipeline navigation."""
    st.markdown("""
    <div class="pipeline-container">
        <div class="pipeline-stage completed">
            <span>📥</span>
            <span>Ingest</span>
        </div>
        <span class="pipeline-arrow">→</span>
        <div class="pipeline-stage completed">
            <span>🔍</span>
            <span>Extract</span>
        </div>
        <span class="pipeline-arrow">→</span>
        <div class="pipeline-stage completed">
            <span>📋</span>
            <span>Summary</span>
        </div>
        <span class="pipeline-arrow">→</span>
        <div class="pipeline-stage completed">
            <span>🔬</span>
            <span>Differential</span>
        </div>
        <span class="pipeline-arrow">→</span>
        <div class="pipeline-stage active">
            <span>✅</span>
            <span>Report</span>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_evidence_badge(eid: str, key_suffix: str = ""):
    """Render a clickable evidence badge."""
    if st.button(f"📎 {eid}", key=f"ev_{eid}_{key_suffix}", help=f"View evidence {eid}"):
        st.session_state["selected_evidence"] = eid
        st.session_state["show_evidence_panel"] = True


def render_summary_section(data: dict):
    """Render the ICU summary section."""
    st.markdown("""
    <div class="clinical-card">
        <div class="clinical-card-header">
            <span class="clinical-card-icon">📋</span>
            <h3>ICU Summary</h3>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    patient_state = data.get("report", {}).get("patient_state", {})
    
    # Diagnoses
    diagnoses = patient_state.get("diagnoses", [])
    if diagnoses:
        st.markdown("**🏷️ Active Problems**")
        for i, dx in enumerate(diagnoses):
            cols = st.columns([4, 1])
            with cols[0]:
                st.markdown(f"• {dx.get('label', '')}")
            with cols[1]:
                for eid in dx.get("evidence_ids", [])[:1]:
                    render_evidence_badge(eid, f"dx_{i}")
    
    # Procedures
    procedures = patient_state.get("procedures", [])
    if procedures:
        st.markdown("**🔧 Procedures/History**")
        for i, proc in enumerate(procedures):
            cols = st.columns([4, 1])
            with cols[0]:
                st.markdown(f"• {proc.get('label', '')}")
            with cols[1]:
                for eid in proc.get("evidence_ids", [])[:1]:
                    render_evidence_badge(eid, f"proc_{i}")
    
    # Key Labs
    timeline = patient_state.get("timeline", [])
    if timeline:
        st.markdown("**🧪 Key Labs**")
        lab_cols = st.columns(3)
        for i, lab in enumerate(timeline[:6]):
            with lab_cols[i % 3]:
                label = lab.get("label", "")
                value = lab.get("value", "")
                st.markdown(f"**{label}:** {value}")


def render_differential_section(data: dict):
    """Render the differential diagnosis section."""
    st.markdown("""
    <div class="clinical-card">
        <div class="clinical-card-header">
            <span class="clinical-card-icon">🔬</span>
            <h3>Differential Diagnosis</h3>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    differential = data.get("report", {}).get("differential", [])
    
    for i, dx in enumerate(differential):
        confidence = dx.get("confidence", "medium")
        conf_class = f"confidence-{confidence}"
        conf_color = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(confidence, "⚪")
        
        with st.expander(f"{conf_color} **{dx.get('diagnosis', '')}** — {confidence.upper()}", expanded=(i < 2)):
            # Supporting Evidence
            st.markdown("**Supporting Evidence:**")
            for s in dx.get("support", []):
                cols = st.columns([3, 2, 1])
                with cols[0]:
                    st.markdown(f"• {s.get('label', '')}")
                with cols[1]:
                    st.caption(s.get('value', ''))
                with cols[2]:
                    for eid in s.get("evidence_ids", [])[:1]:
                        render_evidence_badge(eid, f"supp_{i}_{s.get('label', '')[:10]}")
            
            # Missing
            missing = dx.get("missing", [])
            if missing:
                st.markdown("**Missing (to confirm):**")
                for m in missing:
                    st.markdown(f"  ❓ {m}")


def render_questions_section(data: dict):
    """Render clarifying questions and action items."""
    report = data.get("report", {})
    
    # Clarifying Questions
    st.markdown("""
    <div class="clinical-card">
        <div class="clinical-card-header">
            <span class="clinical-card-icon">❓</span>
            <h3>Clarifying Questions</h3>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    questions = report.get("clarifying_questions", [])
    for i, q in enumerate(questions):
        priority = q.get("priority", "medium")
        priority_colors = {
            "critical": ("🔴", "#fff5f5"),
            "high": ("🟠", "#fffaf0"),
            "medium": ("🟡", "#fffff0"),
            "low": ("🟢", "#f0fff4"),
        }
        color_emoji, bg = priority_colors.get(priority, ("⚪", "#f7fafc"))
        
        st.markdown(f"""
        <div class="action-item" style="background: {bg};">
            <span>{color_emoji}</span>
            <div>
                <strong>{q.get('question', '')}</strong>
                <br><small style="color: #718096;">{q.get('rationale', '')}</small>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Action Items
    st.markdown("""
    <div class="clinical-card">
        <div class="clinical-card-header">
            <span class="clinical-card-icon">✅</span>
            <h3>Recommended Actions</h3>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    actions = report.get("action_items", [])
    for i, a in enumerate(actions):
        priority = a.get("priority", "medium")
        priority_colors = {
            "critical": ("🔴", "#fff5f5"),
            "high": ("🟠", "#fffaf0"),
            "medium": ("🟡", "#fffff0"),
            "low": ("🟢", "#f0fff4"),
        }
        color_emoji, bg = priority_colors.get(priority, ("⚪", "#f7fafc"))
        
        st.markdown(f"""
        <div class="action-item" style="background: {bg};">
            <span>{color_emoji}</span>
            <div>
                <strong>{a.get('item', '')}</strong>
                <br><small style="color: #718096;">{a.get('rationale', '')}</small>
            </div>
        </div>
        """, unsafe_allow_html=True)


def render_evidence_panel(data: dict):
    """Render the evidence viewer panel."""
    store = data.get("evidence_store", {})
    selected = st.session_state.get("selected_evidence", "")
    
    st.markdown("### 📎 Evidence Viewer")
    
    # Evidence ID input
    evidence_id = st.text_input(
        "Enter Evidence ID:",
        value=selected,
        placeholder="e.g., N000001, L000040, M000001",
        key="evidence_input",
    )
    
    if evidence_id:
        st.session_state["selected_evidence"] = evidence_id
        
        if evidence_id in store:
            record = store[evidence_id]
            
            st.markdown(f"""
            <div class="evidence-viewer">
                <div class="evidence-viewer-header">
                    <h4>{evidence_id}</h4>
                    <span class="confidence-badge confidence-high">{record.get('evidence_type', 'unknown')}</span>
                </div>
                <div class="evidence-meta">
                    <span>📁 {record.get('source_file', 'unknown')}</span>
                    <span>📍 Lines {record.get('line_start', '?')}-{record.get('line_end', '?')}</span>
                </div>
                <div class="evidence-content">{record.get('raw_text', '')}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.error(f"Evidence ID not found: {evidence_id}")
    
    # Quick access buttons
    st.markdown("#### Quick Access")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("📝 Narrative", key="nav_btn"):
            st.session_state["evidence_prefix"] = "N"
    with col2:
        if st.button("🧪 Labs", key="lab_btn"):
            st.session_state["evidence_prefix"] = "L"
    with col3:
        if st.button("📊 Monitor", key="mon_btn"):
            st.session_state["evidence_prefix"] = "M"
    
    # Show filtered list
    prefix = st.session_state.get("evidence_prefix", "")
    if prefix:
        st.markdown(f"**{prefix} Evidence:**")
        filtered = sorted([eid for eid in store.keys() if eid.startswith(prefix)])[:8]
        for eid in filtered:
            preview = store[eid].get("raw_text", "")[:40].replace("\n", " ")
            if st.button(f"{eid}: {preview}...", key=f"list_{eid}"):
                st.session_state["selected_evidence"] = eid


def render_sidebar(data: dict):
    """Render the sidebar with navigation and info."""
    with st.sidebar:
        st.markdown("## 🏥 ICU Copilot")
        st.markdown("---")
        
        # Navigation
        st.markdown("### Navigation")
        page = st.radio(
            "Select View:",
            ["📋 Full Report", "🔬 Differential Only", "❓ Questions Only", "📎 Evidence Browser"],
            label_visibility="collapsed",
        )
        
        st.markdown("---")
        
        # Quality Summary
        quality = data.get("quality", {})
        if quality:
            score = quality.get("score", 0)
            passed = quality.get("passed", False)
            status = "✅ PASS" if passed else "⚠️ REVIEW"
            
            st.markdown("### Quality Gate")
            st.markdown(f"""
            <div style="text-align: center; padding: 1rem; background: {'#f0fff4' if passed else '#fffaf0'}; border-radius: 10px;">
                <div style="font-size: 2rem; font-weight: bold; color: {'#22543d' if passed else '#744210'};">{score}</div>
                <div style="font-size: 0.9rem; color: #718096;">{status}</div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Report Info
        st.markdown("### Report Info")
        st.caption(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        st.caption(f"Evidence Records: {len(data.get('evidence_store', {}))}")
        
        st.markdown("---")
        
        # Download
        st.markdown("### Export")
        report_md_path = RUNS_DIR / "report.md"
        if report_md_path.exists():
            with open(report_md_path, "r") as f:
                st.download_button(
                    "📄 Download Report (MD)",
                    f.read(),
                    file_name="icu_report.md",
                    mime="text/markdown",
                )
        
        return page


# ═══════════════════════════════════════════════════════════════════
# Main Application
# ═══════════════════════════════════════════════════════════════════

def main():
    """Main application entry point."""
    # Load data
    data = load_all_data()
    
    if not data.get("report"):
        st.error("❌ No report data found. Please run the pipeline first.")
        st.code("python -m icu_copilot.pipeline.run_llm", language="bash")
        return
    
    # Render header
    render_header()
    
    # Sidebar navigation
    page = render_sidebar(data)
    
    # Main content based on page selection
    if page == "📋 Full Report":
        # Pipeline visualization
        render_pipeline_nav()
        
        # Patient banner
        render_patient_banner(data)
        
        # Quality metrics
        render_quality_metrics(data)
        
        st.markdown("---")
        
        # Two-column layout
        main_col, evidence_col = st.columns([2, 1])
        
        with main_col:
            # Tabs for different sections
            tab1, tab2, tab3 = st.tabs(["📋 Summary", "🔬 Differential", "❓ Questions & Actions"])
            
            with tab1:
                render_summary_section(data)
            
            with tab2:
                render_differential_section(data)
            
            with tab3:
                render_questions_section(data)
        
        with evidence_col:
            render_evidence_panel(data)
    
    elif page == "🔬 Differential Only":
        render_patient_banner(data)
        col1, col2 = st.columns([2, 1])
        with col1:
            render_differential_section(data)
        with col2:
            render_evidence_panel(data)
    
    elif page == "❓ Questions Only":
        render_patient_banner(data)
        col1, col2 = st.columns([2, 1])
        with col1:
            render_questions_section(data)
        with col2:
            render_evidence_panel(data)
    
    elif page == "📎 Evidence Browser":
        st.markdown("## 📎 Evidence Browser")
        st.markdown("Browse all evidence records from the patient chart.")
        
        store = data.get("evidence_store", {})
        
        # Filter
        filter_col1, filter_col2 = st.columns([1, 3])
        with filter_col1:
            prefix_filter = st.selectbox(
                "Type:",
                ["All", "N - Narrative", "L - Labs", "M - Monitor", "F - Flowsheet", "D - Domain"],
            )
        
        # Get filtered evidence
        if prefix_filter == "All":
            filtered = store
        else:
            prefix = prefix_filter[0]
            filtered = {k: v for k, v in store.items() if k.startswith(prefix)}
        
        st.markdown(f"**Showing {len(filtered)} records**")
        
        # Display in grid
        for eid, record in list(filtered.items())[:20]:
            with st.expander(f"📎 {eid} — {record.get('source_file', 'unknown')}"):
                st.markdown(f"**Type:** `{record.get('evidence_type', 'unknown')}`")
                st.markdown(f"**Lines:** {record.get('line_start', '?')} - {record.get('line_end', '?')}")
                st.code(record.get("raw_text", ""), language=None)
    
    # Footer
    st.markdown("---")
    st.caption("🏥 ICU Clinical Decision Support System • AI-assisted analysis with full evidence traceability • For clinical decision support only")


if __name__ == "__main__":
    main()
