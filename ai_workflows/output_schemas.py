RISK_FLAG_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "category": {"type": "string"},
            "severity": {"enum": ["Low", "Medium", "High", "Critical"]},
            "rationale": {"type": "string"},
            "evidence": {"type": "string"},
            "recommendation": {"type": "string"},
            "confidence": {"type": "number"},
            "clause_type": {"type": "string"}
        }
    }
}

SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "content": {"type": "string"},
        "obligation_map": {"type": "array", "items": {"type": "object"}},
        "missing_clauses": {"type": "array", "items": {"type": "object"}}
    }
}
