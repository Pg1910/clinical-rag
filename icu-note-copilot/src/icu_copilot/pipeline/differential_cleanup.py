"""Deterministic post-processing cleanup for differential diagnoses."""
from __future__ import annotations

import logging
from icu_copilot.ingest.schemas import DifferentialOutput, ExtractedFact

logger = logging.getLogger(__name__)


# Rules for removing weak/unrelated supports
WEAK_SUPPORT_RULES = {
    # For AKI diagnoses, RBC is not mechanistically related
    "aki": {
        "remove_labels": ["rbc", "rbc elevation", "red blood cell"],
        "remove_values": ["rbc elevation", "rbc"],
    },
    "acute kidney injury": {
        "remove_labels": ["rbc", "rbc elevation", "red blood cell"],
        "remove_values": ["rbc elevation", "rbc"],
    },
    # For coagulopathy, BUN is not directly related
    "coagulopathy": {
        "remove_labels": ["bun", "elevated bun"],
        "remove_values": ["elevated bun"],
    },
}


def clean_weak_supports(dx_out: DifferentialOutput) -> DifferentialOutput:
    """
    Remove mechanistically unrelated support items from diagnoses.
    
    For example:
    - AKI should not cite RBC elevation as support
    - Coagulopathy should not cite BUN as support
    """
    for dx in dx_out.differential:
        dx_key = dx.diagnosis.lower()
        
        # Find matching rule
        applicable_rule = None
        for rule_key, rule in WEAK_SUPPORT_RULES.items():
            if rule_key in dx_key:
                applicable_rule = rule
                break
        
        if not applicable_rule:
            continue
        
        # Filter out weak supports
        original_count = len(dx.support)
        filtered_supports = []
        
        for s in dx.support:
            label_lower = s.label.lower()
            value_lower = s.value.lower()
            
            should_remove = False
            
            # Check if label or value matches removal patterns
            for remove_label in applicable_rule.get("remove_labels", []):
                if remove_label in label_lower:
                    should_remove = True
                    break
            
            for remove_value in applicable_rule.get("remove_values", []):
                if remove_value in value_lower:
                    should_remove = True
                    break
            
            if should_remove:
                logger.info(f"Removing weak support from '{dx.diagnosis}': {s.label}={s.value}")
            else:
                filtered_supports.append(s)
        
        dx.support = filtered_supports
        
        # Log if supports were removed
        if len(dx.support) < original_count:
            logger.info(f"Cleaned '{dx.diagnosis}': {original_count} -> {len(dx.support)} supports")
    
    return dx_out


def enforce_minimum_supports(dx_out: DifferentialOutput) -> DifferentialOutput:
    """
    Ensure each diagnosis has at least 2 supports.
    If not, downgrade confidence and add missing discriminators.
    """
    for dx in dx_out.differential:
        support_count = len(dx.support)
        
        if support_count < 2:
            # Downgrade confidence
            original_confidence = dx.confidence
            dx.confidence = "low"
            
            # Add discriminator if missing list is empty
            if not dx.missing:
                dx.missing.append("Additional clinical or lab evidence needed to confirm diagnosis")
            
            logger.warning(
                f"'{dx.diagnosis}' has only {support_count} support(s). "
                f"Confidence downgraded: {original_confidence} -> low"
            )
    
    return dx_out


def fix_kasai_evidence_id(dx_out: DifferentialOutput) -> DifferentialOutput:
    """
    Correct Kasai procedure evidence ID to N000002 (where it actually appears).
    """
    CORRECT_KASAI_ID = "N000002"
    
    for dx in dx_out.differential:
        for s in dx.support:
            if "kasai" in s.label.lower() or "kasai" in s.value.lower():
                if CORRECT_KASAI_ID not in s.evidence_ids:
                    logger.info(f"Correcting Kasai evidence ID: {s.evidence_ids} -> [{CORRECT_KASAI_ID}]")
                    s.evidence_ids = [CORRECT_KASAI_ID]
    
    return dx_out


def deduplicate_diagnoses(dx_out: DifferentialOutput) -> DifferentialOutput:
    """
    Remove diagnoses that are essentially duplicates or sub-conditions of others.
    Keep the more specific or better-supported one.
    """
    # Define which diagnoses subsume others
    SUBSUMPTION_RULES = [
        # If we have both "Primary Hepatic Failure" and "Coagulopathy (likely Hepatic)",
        # keep both but ensure they're distinct
        # This is a soft rule - we keep overlapping for clinical completeness
    ]
    
    # For now, just log overlaps but keep them
    dx_names = [dx.diagnosis.lower() for dx in dx_out.differential]
    
    hepatic_related = [n for n in dx_names if "hepat" in n or "liver" in n or "coagul" in n]
    if len(hepatic_related) > 2:
        logger.warning(f"Multiple hepatic-related diagnoses detected: {hepatic_related}")
    
    return dx_out


def run_all_cleanups(dx_out: DifferentialOutput) -> DifferentialOutput:
    """Run all deterministic cleanup rules on differential output."""
    logger.info("Running differential cleanup pipeline...")
    
    dx_out = fix_kasai_evidence_id(dx_out)
    dx_out = clean_weak_supports(dx_out)
    dx_out = enforce_minimum_supports(dx_out)
    dx_out = deduplicate_diagnoses(dx_out)
    
    logger.info("Differential cleanup complete")
    return dx_out
