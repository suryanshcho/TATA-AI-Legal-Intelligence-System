import re

CLAUSE_DEFS = {
    "indemnity": {
        "keys": ["indemnif", "indemnity", "hold harmless"],
        "label": "Indemnification",
    },
    "limitation_of_liability": {
        "keys": ["limitation of liability", "limit of liability", "aggregate liability", "liability cap", "not be liable"],
        "label": "Limitation of Liability",
    },
    "confidentiality": {
        "keys": ["confidential", "non-disclosure", "non disclosure", "proprietary information"],
        "label": "Confidentiality / NDA",
    },
    "termination": {
        "keys": ["terminate", "termination", "right to cancel", "termination for convenience"],
        "label": "Termination",
    },
    "renewal": {
        "keys": ["renew", "auto-renew", "automatic renewal", "automatically renew"],
        "label": "Renewal",
    },
    "payment": {
        "keys": ["payment terms", "invoice", "net 30", "net 60", "late payment", "interest"],
        "label": "Payment Terms",
    },
    "data_protection": {
        "keys": ["data protection", "personal data", "gdp", "privacy", "processing of data", "cross-border"],
        "label": "Data Protection / Privacy",
    },
    "governing_law": {
        "keys": ["governing law", "governed by", "laws of", "jurisdiction of", "shall be construed"],
        "label": "Governing Law",
    },
    "dispute_resolution": {
        "keys": ["dispute resolution", "arbitration", "arbitrate", "mediation", "litigation", "disputes arising"],
        "label": "Dispute Resolution",
    },
    "audit_rights": {
        "keys": ["audit rights", "right to audit", "books and records", "inspect"],
        "label": "Audit Rights",
    },
    "force_majeure": {
        "keys": ["force majeure", "act of god", "beyond reasonable control", "unforeseen"],
        "label": "Force Majeure",
    },
    "assignment": {
        "keys": ["assignment", "assign the agreement", "novation", "transfer of this agreement"],
        "label": "Assignment",
    },
    "non_compete": {
        "keys": ["non-compete", "non compete", "not compete", "competitive business"],
        "label": "Non-Compete",
    },
    "warranty": {
        "keys": ["warrant", "warranty", "represents and warrants", "guarantee"],
        "label": "Warranties",
    },
    "insurance": {
        "keys": ["insurance", "commercial general liability", "policy of insurance"],
        "label": "Insurance",
    },
    "ip_rights": {
        "keys": ["intellectual property", "ip rights", "ownership of", "copyright", "work made for hire", "licens"],
        "label": "Intellectual Property",
    },
    "compliance": {
        "keys": ["compliance", "applicable laws", "regulatory", "anti-bribery", "anti-corruption", "sanction"],
        "label": "Compliance / Regulatory",
    },
    "service_levels": {
        "keys": ["service level", "sla", "uptime", "response time", "availability"],
        "label": "Service Levels",
    },
    "deliverables": {
        "keys": ["deliverable", "milestone", "statement of work", "scope of work"],
        "label": "Deliverables / SOW",
    },
    "entire_agreement": {
        "keys": ["entire agreement", "merger clause", "supersedes"],
        "label": "Entire Agreement",
    },
}


def extract_clauses(text: str, doc_type: str = "Contract") -> list:
    text_lower = text.lower()
    results = []
    for clause_id, spec in CLAUSE_DEFS.items():
        hits = []
        for key in spec["keys"]:
            for m in re.finditer(re.escape(key), text_lower):
                start = max(0, m.start() - 120)
                end = min(len(text), m.end() + 600)
                snippet = " ".join(text[start:end].split())
                hits.append({"key": key, "snippet": snippet, "pos": m.start()})
        if hits:
            best = min(hits, key=lambda h: h["pos"])
            page = estimate_page(text, best["pos"])
            section = find_section(text, best["pos"])
            results.append({
                "clause_type": clause_id,
                "label": spec["label"],
                "clause_text": best["snippet"][:1400],
                "page": page,
                "section": section,
                "involved_parties": "",
                "obligation_owner": "",
                "confidence": round(min(0.95, 0.5 + 0.12 * len(hits)), 2),
                "hits": len(hits),
            })
    results.sort(key=lambda c: c["page"] if c["page"] else 0)
    return results


def estimate_page(text: str, pos: int, lines_per_page=45) -> int:
    line_no = text.count("\n", 0, pos) + 1
    return (line_no // lines_per_page) + 1


def find_section(text: str, pos: int) -> str:
    before = text[:pos]
    lines = before.splitlines()
    for line in reversed(lines[-15:]):
        s = line.strip()
        if s and len(s) < 70:
            return s
    return ""


def detect_missing_clauses(extracted_types: list, doc_type: str) -> list:
    expected = {
        "Contract": ["termination", "payment", "governing_law", "indemnity"],
        "NDA": ["confidentiality", "governing_law", "termination"],
        "Vendor Agreement": ["termination", "payment", "governing_law", "indemnity", "confidentiality"],
        "Service Agreement": ["service_levels", "payment", "termination", "indemnity"],
        "Master Services Agreement": ["termination", "payment", "governing_law", "indemnity", "ip_rights"],
        "Policy Document": ["compliance", "governing_law"],
        "Employment Contract": ["termination", "confidentiality", "non_compete", "compliance"],
    }.get(doc_type, ["termination", "governing_law"])
    present = set(extracted_types)
    missing = []
    for clause in expected:
        if clause not in present:
            missing.append({
                "clause_type": clause,
                "label": CLAUSE_DEFS[clause]["label"] if clause in CLAUSE_DEFS else clause,
                "reason": f"Expected clause '{clause}' not detected in a {doc_type} document",
            })
    return missing
