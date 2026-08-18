import json

from ai_workflows.offline_engine import run_offline_rules
from ai_workflows.prompt_templates import get_prompt_texts


def generate_risk_flags(clauses, missing_clauses, metadata, text, retrieved, llm, doc_type="Contract"):
    if llm.available():
        try:
            sys_p, user_p = get_prompt_texts(doc_type, clauses, metadata, retrieved)
            result = llm.generate(sys_p, user_p, json_mode=True)
            if isinstance(result, list):
                flags = _validate(result)
                return flags or _offline(clauses, missing_clauses, text)
        except Exception:
            pass
    return _offline(clauses, missing_clauses, text)


def _offline(clauses, missing_clauses, text):
    flags = run_offline_rules(clauses, text, "")
    for m in missing_clauses:
        flags.append({
            "category": f"Missing {m['label']}",
            "severity": "Medium",
            "rationale": m["reason"],
            "evidence": "No matching clause text detected in document",
            "recommendation": "Add the missing clause or document an explicit decision to exclude it",
            "confidence": 0.6,
            "clause_type": m["clause_type"],
        })
    return _dedupe(flags)


def _validate(flags):
    cleaned = []
    for f in flags:
        if not isinstance(f, dict):
            continue
        cleaned.append({
            "category": str(f.get("category", "General Risk"))[:120],
            "severity": str(f.get("severity", "Medium")) if f.get("severity") in ("Low", "Medium", "High", "Critical") else "Medium",
            "rationale": str(f.get("rationale", ""))[:600],
            "evidence": str(f.get("evidence", ""))[:1200],
            "recommendation": str(f.get("recommendation", ""))[:400],
            "confidence": max(0.0, min(1.0, float(f.get("confidence", 0.6)))),
            "clause_type": str(f.get("clause_type", "general"))[:80],
        })
    return cleaned


def _dedupe(flags):
    seen = set()
    out = []
    for f in flags:
        key = (f.get("category"), f.get("severity"))
        if key in seen:
            continue
        seen.add(key)
        out.append(f)
    return out
