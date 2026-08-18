import re
from datetime import datetime

PARTY_KEYWORDS = ["company", "corporation", "limited", "ltd", "pvt", "inc", "llc", "partners", "group"]
ROLE_KEYWORDS = {
    "buyer": ["buyer", "customer", "client", "licensee"],
    "vendor": ["vendor", "supplier", "provider", "licensor", "contractor", "service provider"],
}


def extract_metadata(text: str) -> dict:
    parties = _find_parties(text)
    dates = _find_dates(text)
    governing = _find_governing_law(text)
    money = _find_money(text)
    return {
        "parties": parties,
        "dates": dates,
        "governing_law": governing,
        "currency_amounts": money,
        "term_years": _find_term(text),
    }


def _find_parties(text):
    found = []
    for m in re.finditer(r"([A-Z][A-Za-z0-9 &.'()-]{3,60}(?:Company|Corporation|Limited|Ltd|Pvt|Inc|LLC|Group|Partners|Solutions|Technologies|Services|Enterprises|Ventures))", text):
        name = m.group(1).strip()
        if name not in found:
            found.append(name)
        if len(found) >= 6:
            break
    return found


def _find_dates(text):
    dates = []
    patterns = [
        r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4})",
        r"(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})",
        r"(\d{4}-\d{2}-\d{2})",
        r"(\d{1,2}/\d{1,2}/\d{4})",
    ]
    for pat in patterns:
        for m in re.finditer(pat, text):
            if m.group(1) not in dates:
                dates.append(m.group(1))
    return dates[:10]


def _find_governing_law(text):
    m = re.search(r"(?:governed by|governing law|construed in accordance with)\s+(?:the laws of\s+|the substantive laws of\s+|the law of\s+)?([A-Za-z ]{3,30}?)(?:,|\.|;| without)", text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    for country in ["India", "Singapore", "United Kingdom", "United States", "USA", "New York", "England", "UAE", "Dubai"]:
        if re.search(rf"\b{country}\b", text, re.IGNORECASE):
            return country
    return None


def _find_money(text):
    amounts = re.findall(r"(?:USD|US\$|INR|Rs\.?|EUR|GBP|€|£|\$)\s?\d[\d,]*(?:\.\d+)?(?:\s?(?:million|billion|M|B|mn|bn|cr|lakh))?", text, re.IGNORECASE)
    seen = []
    for a in amounts:
        if a not in seen:
            seen.append(a)
    return seen[:10]


def _find_term(text):
    m = re.search(r"(?:term of|for a term of|initial term of)\s+(\d+)\s*(?:\(?\s*(?:one|two|three|four|five|six|seven|eight|nine|ten)\s*\)?)?\s*years?", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None
