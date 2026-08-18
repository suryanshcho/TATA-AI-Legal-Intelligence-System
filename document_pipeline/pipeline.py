import logging
from datetime import datetime

from backend import audit
from backend.database import db
from backend.config import settings

from document_pipeline import ocr as ocr_service
from document_pipeline import parsing as parsing_service
from document_pipeline import clause_extraction as clause_service
from document_pipeline import normalization as norm_service
from document_pipeline import quality_checks as quality_service

from ai_workflows.rag_retrieval import build_knowledge_index, retrieve
from ai_workflows.legal_reasoning import generate_risk_flags
from ai_workflows.summarization import generate_summary
from ai_workflows.llm_client import LLMClient

logger = logging.getLogger("pipeline")

STAGES = ["upload", "ocr", "parsing", "clause_extraction", "rag_retrieval",
          "legal_reasoning", "risk_flagging", "summarization", "review"]


def run_pipeline(document_id: int):
    with db() as conn:
        doc = conn.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
        if not doc:
            return
        doc = dict(doc)
        conn.execute("UPDATE documents SET status='processing', progress=5, stage='ocr', updated_at=? WHERE id=?",
                     (datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), document_id))

    audit.log(actor="system", action="pipeline_start", entity="document", document_id=document_id,
              detail=f"Job started for {doc['original_name']}")

    try:
        _stage("ocr", document_id)
        from backend import storage
        file_path = str(storage.get_path(doc["filename"]))
        ocr_result = ocr_service.extract_text(file_path, doc["file_type"])
        text = ocr_result["text"]
        _save_job_status(document_id, "ocr_result", ocr_result)
        _mark_stage("ocr", document_id, "done", detail=f"engine={ocr_result['engine']} conf={ocr_result['confidence']} pages={ocr_result['pages']}")

        _stage("parsing", document_id)
        parsed = parsing_service.parse_document(text)
        _mark_stage("parsing", document_id, "done", detail=f"sections={parsed['section_count']} words={parsed['word_count']}")

        _stage("clause_extraction", document_id)
        clauses = clause_service.extract_clauses(text, doc["doc_type"])
        missing = clause_service.detect_missing_clauses([c["clause_type"] for c in clauses], doc["doc_type"])
        _save_clauses(document_id, clauses)
        _mark_stage("clause_extraction", document_id, "done", detail=f"clauses={len(clauses)}")

        _stage("rag_retrieval", document_id)
        build_knowledge_index()
        retrieved = retrieve(join_clause_text(clauses), doc["doc_type"], top_k=settings.TOP_K_RETRIEVAL)
        _save_job_status(document_id, "retrieval_context", retrieved)
        _mark_stage("rag_retrieval", document_id, "done", detail=f"references={len(retrieved)}")

        _stage("legal_reasoning", document_id)
        metadata = norm_service.extract_metadata(text)
        _save_job_status(document_id, "metadata", metadata)

        _stage("risk_flagging", document_id)
        llm = LLMClient()
        risk_flags = generate_risk_flags(clauses, missing, metadata, text, retrieved, llm, doc["doc_type"])
        _save_risks(document_id, clauses, risk_flags)
        high = sum(1 for r in risk_flags if r.get("severity") in ("High", "Critical"))
        _mark_stage("risk_flagging", document_id, "done", detail=f"flags={len(risk_flags)} high={high}")

        _stage("summarization", document_id)
        summary = generate_summary(clauses, missing, metadata, risk_flags, text, llm, doc["doc_type"])
        _save_summary(document_id, summary)
        _mark_stage("summarization", document_id, "done")

        quality = quality_service.assess_quality(text, ocr_result["confidence"], ocr_result.get("warnings", []))
        _save_job_status(document_id, "quality", quality)

        final_status = "completed"
        if high > 0:
            final_status = "attention"
        with db() as conn:
            conn.execute(
                "UPDATE documents SET status=?, progress=100, stage='review', ocr_confidence=?, updated_at=? WHERE id=?",
                (final_status, ocr_result["confidence"], datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), document_id))
        audit.log(actor="system", action="pipeline_complete", entity="document", document_id=document_id,
                  detail=f"Final status={final_status} flags={len(risk_flags)}")
    except Exception as exc:
        logger.exception("Pipeline failed for document %s", document_id)
        _mark_stage("error", document_id, "failed", detail=str(exc))
        with db() as conn:
            conn.execute("UPDATE documents SET status='failed', error=?, updated_at=? WHERE id=?",
                         (str(exc), datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), document_id))
        audit.log(actor="system", action="pipeline_failed", entity="document", document_id=document_id, detail=str(exc))


def _stage(name, document_id):
    with db() as conn:
        conn.execute("UPDATE documents SET progress=?, stage=?, updated_at=? WHERE id=?",
                     (_progress(name), name, datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), document_id))


def _mark_stage(name, document_id, status, detail=None):
    audit.record_stage(document_id, name, status, detail)


def _progress(stage):
    idx = STAGES.index(stage) if stage in STAGES else 0
    return int(8 + (idx / (len(STAGES) - 1)) * 80)


def _save_job_status(document_id, key, value):
    import json
    with db() as conn:
        conn.execute("INSERT OR REPLACE INTO job_status (document_id, key, value) VALUES (?,?,?)",
                     (document_id, key, json.dumps(value, default=str)))


def _save_clauses(document_id, clauses):
    with db() as conn:
        conn.execute("DELETE FROM clauses WHERE document_id=?", (document_id,))
        for c in clauses:
            conn.execute(
                "INSERT INTO clauses (document_id, clause_type, clause_text, page, section, confidence) VALUES (?,?,?,?,?,?)",
                (document_id, c["clause_type"], c["clause_text"], c.get("page"), c.get("section"), c.get("confidence", 0)))


def _save_risks(document_id, clauses, risk_flags):
    clause_map = {}
    with db() as conn:
        rows = conn.execute("SELECT id, clause_type FROM clauses WHERE document_id=?", (document_id,)).fetchall()
        for r in rows:
            clause_map[r["clause_type"]] = r["id"]
        conn.execute("DELETE FROM risk_flags WHERE document_id=?", (document_id,))
        for rf in risk_flags:
            conn.execute(
                "INSERT INTO risk_flags (document_id, clause_id, category, severity, rationale, evidence, recommendation, confidence) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (document_id, clause_map.get(rf.get("clause_type"), None), rf.get("category"), rf.get("severity"),
                 rf.get("rationale"), rf.get("evidence"), rf.get("recommendation"), rf.get("confidence", 0)))


def _save_summary(document_id, summary):
    import json
    with db() as conn:
        conn.execute("DELETE FROM summaries WHERE document_id=?", (document_id,))
        conn.execute(
            "INSERT INTO summaries (document_id, content, obligation_map, missing_clauses, approval_status) VALUES (?,?,?,?,?)",
            (document_id, summary.get("content", ""), json.dumps(summary.get("obligation_map", [])),
             json.dumps(summary.get("missing_clauses", [])), "pending"))


def join_clause_text(clauses):
    return " ".join(c["clause_text"] for c in clauses)
