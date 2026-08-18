import json

SUMMARY_SYSTEM = """You are the summarization engine of the Tata Group AI Legal Document Intelligence System.
Generate a concise, review-ready legal summary. Rules:
1. Base every statement on the extracted clauses or document evidence.
2. Include parties, term, dates, obligations, risks, and missing clauses.
3. Mark the output as SYSTEM-GENERATED and PENDING LEGAL REVIEW.
4. Do not present opinions as final legal advice.
Return valid JSON matching the schema: {"content": string, "obligation_map": [{"clause": string, "obligation": string, "party": string}], "missing_clauses": [{"clause": string, "reason": string}]}"""

SUMMARY_USER = """Document type: {doc_type}
EXTRACTED CLAUSES:
{clauses}
METADATA:
{metadata}
RISK FLAGS:
{risks}
MISSING CLAUSES:
{missing}
TASK: Produce the summary JSON described in the schema."""


def generate_summary(clauses, missing_clauses, metadata, risk_flags, text, llm, doc_type="Contract"):
    if llm.available():
        try:
            user_p = SUMMARY_USER.format(
                doc_type=doc_type,
                clauses=json.dumps(clauses, default=str)[:6000],
                metadata=json.dumps(metadata, default=str)[:1500],
                risks=json.dumps([{k: r[k] for k in ("category", "severity", "rationale") if k in r} for r in risk_flags], default=str)[:2500],
                missing=json.dumps(missing_clauses, default=str)[:1200],
            )
            result = llm.generate(SUMMARY_SYSTEM, user_p, json_mode=True)
            if isinstance(result, dict) and result.get("content"):
                return {
                    "content": str(result["content"]),
                    "obligation_map": result.get("obligation_map", []),
                    "missing_clauses": result.get("missing_clauses", missing_clauses),
                }
        except Exception:
            pass
    return _offline_summary(clauses, missing_clauses, metadata, risk_flags)


def _offline_summary(clauses, missing_clauses, metadata, risk_flags):
    parties = metadata.get("parties", []) or []
    dates = metadata.get("dates", []) or []
    governing = metadata.get("governing_law") or "not specified"
    term = metadata.get("term_years")

    lines = []
    lines.append("SYSTEM-GENERATED SUMMARY - PENDING LEGAL REVIEW")
    lines.append("")
    if parties:
        lines.append("Parties: " + "; ".join(parties))
    if dates:
        lines.append("Key dates: " + ", ".join(dates[:5]))
    if term:
        lines.append(f"Term: {term} year(s)")
    lines.append(f"Governing law: {governing}")
    lines.append("")

    obligation_map = []
    for c in clauses:
        short = c.get("clause_text", "")
        if len(short) > 260:
            short = short[:257] + "..."
        obligation_map.append({
            "clause": c.get("label") or c.get("clause_type"),
            "obligation": short,
            "party": c.get("involved_parties") or "both parties",
        })

    lines.append("Key clauses identified:")
    for o in obligation_map:
        lines.append(f"- {o['clause']}: {o['obligation']}")

    if risk_flags:
        lines.append("")
        lines.append("Risk highlights:")
        high = [r for r in risk_flags if r.get("severity") in ("High", "Critical")]
        for r in (high or risk_flags[:5]):
            lines.append(f"- [{r.get('severity')}] {r.get('category')}: {r.get('rationale')}")

    if missing_clauses:
        lines.append("")
        lines.append("Missing/expected clauses:")
        for m in missing_clauses:
            lines.append(f"- {m.get('label') or m.get('clause_type')}: {m.get('reason')}")

    lines.append("")
    lines.append("NOTE: This summary is AI-generated and requires review and approval by a qualified legal professional before use.")

    return {
        "content": "\n".join(lines),
        "obligation_map": obligation_map,
        "missing_clauses": missing_clauses,
    }
