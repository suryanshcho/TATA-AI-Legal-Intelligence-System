import json
import math
import re
from collections import Counter

from backend.config import DATA_DIR, settings

CLAUDE_LIBRARY_FILE = DATA_DIR / "clause_library" / "clause_library.json"
POLICY_FILE = DATA_DIR / "policy_references" / "policy_references.json"

_INDEX = {"items": [], "tfidf": None}


def _tokenize(text):
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 1]


def _load_items():
    if _INDEX["items"]:
        return _INDEX["items"]
    items = []
    for path in (CLAUDE_LIBRARY_FILE, POLICY_FILE):
        with open(path, encoding="utf-8") as f:
            for it in json.load(f):
                it["_tokens"] = _tokenize(it["content"] + " " + it["title"])
                items.append(it)
    _INDEX["items"] = items
    return items


def build_knowledge_index():
    items = _load_items()
    _INDEX["tfidf"] = _build_tfidf(items)
    return len(items)


def _build_tfidf(items):
    doc_freq = Counter()
    for it in items:
        for tok in set(it["_tokens"]):
            doc_freq[tok] += 1
    idf = {tok: math.log(len(items) / (1 + freq)) for tok, freq in doc_freq.items()}
    weights = []
    for it in items:
        tf = Counter(it["_tokens"])
        total = len(it["_tokens"]) or 1
        vec = {tok: (count / total) * idf.get(tok, 0) for tok, count in tf.items()}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1
        weights.append({tok: v / norm for tok, v in vec.items()})
    return weights


def retrieve(query: str, doc_type: str = None, top_k: int = None) -> list:
    top_k = top_k or settings.TOP_K_RETRIEVAL
    items = _load_items()
    if not items or not _INDEX["tfidf"]:
        return []
    q_tokens = _tokenize(query)
    if not q_tokens:
        return []
    q_counter = Counter(q_tokens)
    total = len(q_tokens)
    all_tokens = set()
    for it in items:
        all_tokens.update(it["_tokens"])
    idf = _infer_idf(all_tokens, items)
    q_vec = {}
    for tok, count in q_counter.items():
        q_vec[tok] = (count / total) * idf.get(tok, 1)
    q_norm = math.sqrt(sum(v * v for v in q_vec.values())) or 1
    q_vec = {tok: v / q_norm for tok, v in q_vec.items()}

    scored = []
    for idx, it in enumerate(items):
        score = sum(it_v * q_vec.get(tok, 0) for tok, it_v in _INDEX["tfidf"][idx].items())
        if doc_type and it.get("doc_type") and doc_type not in ("", "Contract"):
            if it["doc_type"] != doc_type:
                score *= 0.85
        scored.append((score, it))
    scored.sort(key=lambda x: x[0], reverse=True)
    results = []
    for score, it in scored[:top_k]:
        if score <= 0:
            continue
        results.append({
            "title": it["title"],
            "category": it["category"],
            "kind": it["kind"],
            "content": it["content"],
            "source": it["source"],
            "approved": it.get("approved", 1),
            "score": round(score, 4),
        })
    return results


def _infer_idf(all_tokens, items):
    doc_freq = Counter()
    for it in items:
        for tok in set(it["_tokens"]):
            doc_freq[tok] += 1
    return {tok: math.log(len(items) / (1 + freq)) for tok, freq in doc_freq.items()}


def load_all_knowledge() -> list:
    items = _load_items()
    return [
        {k: v for k, v in it.items() if not k.startswith("_")}
        for it in items
    ]
