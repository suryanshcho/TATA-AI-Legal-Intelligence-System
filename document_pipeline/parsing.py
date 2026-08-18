import re

SECTION_PATTERNS = [
    r"^(\d+(?:\.\d+)*)\s+[A-Z][A-Z0-9 ]{3,}$",
    r"^\d+\.\d+\s+[A-Za-z][A-Za-z0-9 ]{3,}$",
    r"^Section\s+[\d.]+[:\-]?\s*[A-Za-z]",
    r"^Clause\s+[\d.]+[:\-]?\s*[A-Za-z]",
    r"^Art(?:icle)?\.?\s+\d+[:\-]?\s*[A-Za-z]",
    r"^[A-Z][A-Z0-9 &()'/-]{6,}$",
]

HEADINGS = [
    "definitions", "purpose", "scope", "term", "termination", "payment", "fees",
    "indemnification", "indemnity", "limitation of liability", "liability",
    "confidentiality", "data protection", "privacy", "governing law", "jurisdiction",
    "dispute resolution", "arbitration", "assignment", "force majeure", "non-compete",
    "warranty", "warranties", "insurance", "audit rights", "compliance", "notice",
    "intellectual property", "renewal", "representation", "obligations",
    "deliverables", "service levels", "acceptance", "penalty", "milestones",
    "signature", "annexure", "schedule", "exhibit", "miscellaneous", "entire agreement",
]


def parse_document(text: str) -> dict:
    lines = text.splitlines()
    sections = []
    current = {"title": "Preamble", "lines": []}
    for raw in lines:
        line = raw.strip()
        if not line:
            current["lines"].append("")
            continue
        if _is_heading(line):
            if current["lines"]:
                sections.append({**current, "text": "\n".join(current["lines"]).strip()})
            current = {"title": line, "lines": []}
        else:
            current["lines"].append(line)
    if current["lines"]:
        sections.append({**current, "text": "\n".join(current["lines"]).strip()})

    blocks = []
    for idx, sec in enumerate(sections):
        blocks.append({
            "index": idx,
            "title": sec["title"],
            "text": sec["text"],
            "char_start": text.find(sec["text"]) if sec["text"] else -1,
        })
    return {
        "sections": blocks,
        "section_count": len(blocks),
        "word_count": len(text.split()),
        "char_count": len(text),
    }


def _is_heading(line: str) -> bool:
    if not line or len(line) < 4 or len(line) > 90:
        return False
    lower = line.lower().strip(" .:")
    if any(h in lower for h in HEADINGS) and len(line) < 60:
        return True
    for pat in SECTION_PATTERNS:
        if re.match(pat, line):
            return True
    return False
