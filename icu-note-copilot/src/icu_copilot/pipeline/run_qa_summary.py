"""
Tactical Q&A Summary Runner

Produces a text-based clinical summary in Question-Answering format.
Uses the question templates to query the RAG system and LLM.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from icu_copilot.logging_conf import setup_logging
from icu_copilot.config import SETTINGS
from icu_copilot.llm.client import OllamaClient, truncate_evidence_list, estimate_tokens
from icu_copilot.llm.question_templates import QUESTION_TEMPLATES
from icu_copilot.rag.retrieve import HybridRetriever


# ============================================================================
# Q&A PROMPTS
# ============================================================================

QA_SYSTEM_PROMPT = """You are a clinical decision support assistant answering specific questions about an ICU patient.

RULES:
1. Answer ONLY based on the provided evidence.
2. Cite evidence IDs in brackets [N000001] when making claims.
3. If the evidence does not contain the answer, say "Not documented in available records."
4. Be concise but thorough. Use clinical terminology.
5. Do NOT fabricate or infer data not in the evidence.
"""

QA_PROMPT_TEMPLATE = """
QUESTION: {question}

CONTEXT (Patient Evidence):
{evidence}

Provide a clear, evidence-based answer. Cite evidence IDs in brackets.
"""


# ============================================================================
# Q&A RUNNER
# ============================================================================

class QASummaryRunner:
    """Runs Q&A-based clinical summarization."""
    
    def __init__(self, indices_dir: Path, runs_dir: Path):
        self.indices_dir = indices_dir
        self.runs_dir = runs_dir
        self.retriever = HybridRetriever(indices_dir)
        self.llm = OllamaClient()
        self.logger = logging.getLogger(__name__)
    
    def _retrieve_for_question(self, question: str, top_k: int = 12) -> str:
        """Retrieve relevant evidence for a specific question."""
        results = self.retriever.hybrid_search(question, top_k=top_k)
        
        evs = [{"evidence_id": r.evidence_id, "text": r.text} for r in results]
        return truncate_evidence_list(evs, max_total_chars=SETTINGS.max_evidence_chars // 2)
    
    def _answer_question(self, question: str, evidence: str) -> str:
        """Get LLM answer to a specific question."""
        prompt = f"{QA_SYSTEM_PROMPT}\n\n{QA_PROMPT_TEMPLATE.format(question=question, evidence=evidence)}"
        
        self.logger.info(f"Q&A prompt: {len(prompt)} chars (~{estimate_tokens(prompt)} tokens)")
        
        try:
            response = self.llm.generate(prompt, json_mode=False)
            return response.strip()
        except Exception as e:
            self.logger.error(f"LLM error: {e}")
            return f"[Error generating answer: {e}]"
    
    def run_all_questions(self) -> List[Dict[str, Any]]:
        """Run all question templates and collect answers."""
        results = []
        
        for template in QUESTION_TEMPLATES:
            qid = template["id"]
            question = template["template"]
            rationale = template["rationale"]
            
            self.logger.info(f"Processing question: {qid}")
            
            # Retrieve relevant evidence
            evidence = self._retrieve_for_question(question)
            
            # Get LLM answer
            answer = self._answer_question(question, evidence)
            
            results.append({
                "id": qid,
                "question": question,
                "rationale": rationale,
                "answer": answer,
            })
        
        return results
    
    def format_text_output(self, qa_results: List[Dict[str, Any]]) -> str:
        """Format Q&A results as readable text."""
        lines = []
        
        # Header
        lines.append("=" * 80)
        lines.append("ICU CLINICAL SUMMARY - QUESTION & ANSWER FORMAT")
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("=" * 80)
        lines.append("")
        
        # Each Q&A section
        for i, qa in enumerate(qa_results, 1):
            lines.append(f"─" * 80)
            lines.append(f"Q{i}. [{qa['id'].upper()}]")
            lines.append(f"─" * 80)
            lines.append("")
            lines.append(f"QUESTION:")
            lines.append(f"  {qa['question']}")
            lines.append("")
            lines.append(f"CLINICAL RATIONALE:")
            lines.append(f"  {qa['rationale']}")
            lines.append("")
            lines.append(f"ANSWER:")
            # Indent the answer
            for line in qa['answer'].split('\n'):
                lines.append(f"  {line}")
            lines.append("")
            lines.append("")
        
        # Footer
        lines.append("=" * 80)
        lines.append("END OF CLINICAL Q&A SUMMARY")
        lines.append("=" * 80)
        
        return "\n".join(lines)
    
    def run(self) -> Path:
        """Execute the full Q&A pipeline and save outputs."""
        self.logger.info("Starting Q&A Summary Pipeline...")
        
        # Run all questions
        qa_results = self.run_all_questions()
        
        # Create output directory
        run_dir = self.runs_dir / "latest"
        run_dir.mkdir(parents=True, exist_ok=True)
        
        # Save JSON output
        json_path = run_dir / "qa_summary.json"
        json_path.write_text(json.dumps(qa_results, indent=2), encoding="utf-8")
        self.logger.info(f"Saved JSON: {json_path}")
        
        # Save text output
        text_output = self.format_text_output(qa_results)
        text_path = run_dir / "qa_summary.txt"
        text_path.write_text(text_output, encoding="utf-8")
        self.logger.info(f"Saved Text: {text_path}")
        
        # Print to console
        print("\n" + text_output)
        
        self.logger.info("Q&A Summary Pipeline Complete!")
        return text_path


# ============================================================================
# ADDITIONAL CLINICAL QUESTIONS
# ============================================================================

EXTENDED_QUESTIONS = [
    {
        "id": "patient_overview",
        "template": "What is the patient's age, weight, and primary admission diagnosis?",
        "rationale": "Establishes baseline patient context for clinical decision-making.",
    },
    {
        "id": "current_status",
        "template": "What is the patient's current clinical status and trajectory (improving, stable, deteriorating)?",
        "rationale": "Guides urgency of interventions and prognosis discussion.",
    },
    {
        "id": "organ_failures",
        "template": "Which organ systems are currently failing or at risk, and what is the evidence?",
        "rationale": "Multi-organ dysfunction assessment is critical in ICU patients.",
    },
    {
        "id": "ventilator_settings",
        "template": "What are the current ventilator settings (mode, FiO2, PEEP, tidal volume) and respiratory status?",
        "rationale": "Essential for ARDS management and weaning readiness assessment.",
    },
    {
        "id": "hemodynamics",
        "template": "What are the patient's hemodynamic parameters (MAP, heart rate, vasopressor requirements)?",
        "rationale": "Guides fluid resuscitation and vasopressor management in sepsis/shock.",
    },
    {
        "id": "antibiotic_coverage",
        "template": "What antibiotics is the patient receiving and are they appropriate for the identified organisms?",
        "rationale": "Antibiotic stewardship and source control are pillars of sepsis management.",
    },
]


def get_all_questions() -> List[Dict[str, str]]:
    """Combine base and extended questions."""
    return QUESTION_TEMPLATES + EXTENDED_QUESTIONS


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main() -> None:
    """Run the Q&A summary pipeline."""
    setup_logging(logging.INFO)
    
    root = Path(__file__).resolve().parents[3]
    indices_dir = root / "data" / "indices"
    processed_dir = root / "data" / "processed"
    runs_dir = processed_dir / "runs"
    
    # Temporarily extend with additional questions
    import icu_copilot.llm.question_templates as qt
    original_templates = qt.QUESTION_TEMPLATES.copy()
    qt.QUESTION_TEMPLATES.extend(EXTENDED_QUESTIONS)
    
    try:
        runner = QASummaryRunner(indices_dir, runs_dir)
        output_path = runner.run()
        
        logging.info("=" * 50)
        logging.info("Q&A SUMMARY COMPLETE")
        logging.info(f"Output saved to: {output_path}")
        logging.info("=" * 50)
    finally:
        # Restore original templates
        qt.QUESTION_TEMPLATES[:] = original_templates


if __name__ == "__main__":
    main()
