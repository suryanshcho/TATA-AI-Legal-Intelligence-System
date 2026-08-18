import csv
import re

from backend.config import DATA_DIR

TAXONOMY_FILE = DATA_DIR / "risk_taxonomy.csv"
_TAXONOMY = None


def load_taxonomy():
    global _TAXONOMY
    if _TAXONOMY is not None:
        return _TAXONOMY
    rules = []
    with open(TAXONOMY_FILE, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            row["pattern_re"] = re.compile(row["pattern"].strip().lower())
            rules.append(row)
    _TAXONOMY = rules
    return rules


def run_offline_rules(clauses: list, text: str, doc_type: str) -> list:
    rules = load_taxonomy()
    text_lower = text.lower()
    flags = []
    matched_rules = set()

    for clause in clauses:
        clause_text = clause.get("clause_text", "").lower()
        for rule in rules:
            if rule["clause_type"] and clause["clause_type"] != rule["clause_type"]:
                continue
            if rule["category"] in matched_rules:
                continue
            hit, evidence = _match_rule(rule, clause_text, clause.get("section") or "")
            if hit:
                matched_rules.add(rule["category"])
                flags.append({
                    "category": rule["category"],
                    "severity": rule["severity"],
                    "rationale": rule["rationale"],
                    "evidence": evidence[:1200],
                    "recommendation": rule["recommendation"],
                    "confidence": float(rule["confidence"]),
                    "clause_type": clause["clause_type"],
                })
                break

    if not flags:
        for rule in rules:
            pattern = rule["pattern"].strip().lower()
            if pattern.startswith("^$") and rule["clause_type"]:
                types = {c["clause_type"] for c in clauses}
                if rule["clause_type"] not in types:
                    flags.append({
                        "category": rule["category"],
                        "severity": rule["severity"],
                        "rationale": rule["rationale"],
                        "evidence": "No matching clause text found in document",
                        "recommendation": rule["recommendation"],
                        "confidence": float(rule["confidence"]),
                        "clause_type": rule["clause_type"],
                    })
                    matched_rules.add(rule["category"])
    return flags


def _match_rule(rule, clause_text, section_text):
    search_blob = f"{clause_text} {section_text}".lower()
    m = rule["pattern_re"].search(search_blob)
    if not m:
        return False, ""
    start = max(0, m.start() - 100)
    end = min(len(clause_text), m.end() + 220)
    snippet = clause_text[start:end].strip()
    if not snippet:
        snippet = search_blob[max(0, start):].strip()[:1200]
    return True, snippet
