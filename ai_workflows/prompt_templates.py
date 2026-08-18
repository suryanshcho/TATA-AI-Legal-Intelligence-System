import json

from backend.database import db

SYSTEM_PROMPT = """You are the legal reasoning engine of the Tata Group AI Legal Document Intelligence System.
You analyze legal documents for enterprise legal and compliance review. You must follow strict rules:
1. ONLY flag risks that are supported by the extracted document evidence or retrieved approved knowledge.
2. Each risk flag MUST include: category, severity (Low/Medium/High/Critical), rationale, evidence (exact language from the document), recommendation, confidence (0-1), and clause_type.
3. Never present conclusions as final legal advice. Mark outputs as system-generated and pending legal review.
4. If evidence is insufficient, do not invent risk flags.
5. Use the retrieved approved references to validate positions.
Return valid JSON matching the schema.""";

REASONING_PROMPT = """Document type: {doc_type}

EXTRACTED CLAUSES:
{clauses}

RETRIEVED APPROVED REFERENCES:
{references}

DOCUMENT METADATA:
{metadata}

TASK: Produce a JSON array of risk flags. Base every flag on the extracted clause text or retrieved references.
Include a flag if a clause is missing that should exist, if language is unusual, one-sided, high-risk, or conflicts with approved positions.
Never fabricate evidence. Keep rationale concise and business-readable."""


def get_prompt_texts(doc_type, clauses, metadata, references):
    clauses_text = json.dumps(clauses, indent=1, default=str)[:6000]
    refs_text = "\n".join(f"- [{r['title']}]: {r['content'][:400]}" for r in references[:5])
    meta_text = json.dumps(metadata, default=str)[:1200]
    return SYSTEM_PROMPT, REASONING_PROMPT.format(doc_type=doc_type, clauses=clauses_text,
                                                  references=refs_text, metadata=meta_text)


def get_ai_mode():
    with db() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key='ai_mode'").fetchone()
        return row["value"] if row else "auto"
