def assess_quality(text: str, ocr_confidence: float, warnings: list) -> dict:
    checks = {"readable": True, "issues": list(warnings or [])}
    word_count = len(text.split()) if text else 0
    if word_count < 50:
        checks["readable"] = False
        checks["issues"].append("Very little text extracted - document may be unreadable")
    if ocr_confidence < 50:
        checks["issues"].append("OCR confidence below 50% - manual review recommended")
    if ocr_confidence > 0 and ocr_confidence < 80:
        checks["issues"].append("OCR confidence between 50-80% - verify extracted clauses")
    checks["word_count"] = word_count
    checks["ocr_confidence"] = round(ocr_confidence, 1)
    checks["quality_score"] = _score(ocr_confidence, word_count, len(checks["issues"]))
    return checks


def _score(ocr_conf, words, issues) -> int:
    score = 60
    if ocr_conf >= 80:
        score += 25
    elif ocr_conf >= 50:
        score += 10
    if words >= 300:
        score += 10
    elif words >= 100:
        score += 5
    score -= min(30, issues * 6)
    return max(5, min(99, score))
