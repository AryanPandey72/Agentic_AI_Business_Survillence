# agents/verification_engine.py
import re
from difflib import SequenceMatcher
from pydantic import BaseModel
from typing import Dict, Any, Optional, List

# ==========================================
# 1. SCHEMAS
# ==========================================
class PricingRecord(BaseModel):
    vendor: str
    product: str
    plan: str
    billing_cycle: str
    metric: str
    value: str
    unit: str
    source_section: str

class CandidateClaim(BaseModel):
    claim_id: str
    vendor: str
    product: str
    plan: str
    billing_cycle: str
    metric: str
    old_value: str
    new_value: str
    unit: str

# ==========================================
# 2. DETERMINISTIC NORMALIZATION ENGINE
# ==========================================

# Maps non-numeric text limits to comparable math values
ENUM_WEIGHTS = {
    "unlimited": 999_999_999.0,
    "fair_use":  500_000_000.0,
    "contact_sales": -1.0, # Special flag indicating gated features
    "custom": -1.0
}

def parse_to_number(val_str: str) -> float:
    """
    Fixes the 'Formatting Illusion'. 
    Converts '10k', '10,000', and 'Unlimited' into standard math floats.
    """
    if not val_str:
        return 0.0
        
    clean_str = val_str.lower().strip()
    
    # Check for text-based enum limits
    for key, weight in ENUM_WEIGHTS.items():
        if key in clean_str.replace(" ", "_"):
            return weight

    # Strip currency symbols and commas
    clean_str = re.sub(r'[$,]', '', clean_str)
    
    # Handle K, M, B suffixes
    multiplier = 1.0
    if 'k' in clean_str:
        multiplier = 1_000.0
        clean_str = clean_str.replace('k', '')
    elif 'm' in clean_str:
        multiplier = 1_000_000.0
        clean_str = clean_str.replace('m', '')
        
    try:
        # Extract just the numeric part
        numeric_part = re.search(r"[-+]?\d*\.\d+|\d+", clean_str)
        if numeric_part:
            return float(numeric_part.group()) * multiplier
        return 0.0
    except ValueError:
        return 0.0

def values_are_mathematically_equal(val1: str, val2: str) -> bool:
    """Safely checks if '10k' equals '10,000'."""
    return parse_to_number(val1) == parse_to_number(val2)

# ==========================================
# 3. ADVANCED MATCHING (FEATURE UNBUNDLING)
# ==========================================

def get_string_similarity(a: str, b: str) -> float:
    """Returns a ratio from 0.0 to 1.0."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def find_matching_record(claim: CandidateClaim, current_records: List[PricingRecord]) -> Dict[str, Any]:
    """
    Finds exact matches, and safely handles Feature Unbundling 
    (e.g., 'Bandwidth' becoming 'Egress Bandwidth').
    """
    best_match = None
    highest_similarity = 0.0

    for record in current_records:
        # Hard limits that must exactly match
        if (
            record.vendor.lower() == claim.vendor.lower() and
            record.product.lower() == claim.product.lower() and
            record.plan.lower() == claim.plan.lower() and
            record.billing_cycle.lower() == claim.billing_cycle.lower() # Prevents Toggle Traps
        ):
            # Check metric similarity
            similarity = get_string_similarity(record.metric, claim.metric)
            
            if similarity == 1.0:
                return {"status": "exact_match", "record": record}
            
            if similarity > highest_similarity:
                highest_similarity = similarity
                best_match = record

    # If it's very close but not exact, we caught an unbundled metric
    if highest_similarity > 0.70:
        return {"status": "metric_split", "record": best_match}

    return {"status": "not_found", "record": None}

# ==========================================
# 4. THE MASTER VERIFIER
# ==========================================

def verify_pricing_claim(claim_dict: dict, current_records_dict: list) -> Dict[str, Any]:
    """The entry point for the orchestrator."""
    claim = CandidateClaim(**claim_dict)
    current_records = [PricingRecord(**r) for r in current_records_dict]
    
    print(f"Auditing Claim: {claim.vendor} - {claim.metric} changed from {claim.old_value} to {claim.new_value}")

    match_result = find_matching_record(claim, current_records)
    matched_record = match_result["record"]

    # 1. Handle Missing/Unbundled Features
    if match_result["status"] == "not_found":
        return {"classification": "false_positive", "reason": "Metric not found in current UI state."}
        
    if match_result["status"] == "metric_split":
        return {
            "classification": "needs_human_review", 
            "reason": f"Metric Split Detected. '{claim.metric}' likely renamed to '{matched_record.metric}'."
        }

    # 2. Check the Math (Formatting Illusion Fix)
    if not values_are_mathematically_equal(claim.new_value, matched_record.value):
        return {
            "classification": "false_positive",
            "reason": f"Math Mismatch: LLM claimed {claim.new_value}, but deterministic record is {matched_record.value}"
        }

    return {
        "classification": "verified",
        "current_fact_verified": True,
        "matched_record": matched_record.dict(),
        "reason": "Deterministically verified."
    }

# Quick Test Block
if __name__ == "__main__":
    # Testing the Formatting Illusion
    print(f"10k == 10,000? {values_are_mathematically_equal('10k', '10,000')}")
    
    # Testing Unlimited to Fair Use
    print(f"Unlimited > Fair Use? {parse_to_number('Unlimited Storage') > parse_to_number('Fair Use Applies')}")