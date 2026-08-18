import threading

from fastapi import APIRouter, Depends, HTTPException, Request

from backend import audit
from backend.database import db
from backend.schemas import DocumentCreate
from document_pipeline.pipeline import run_pipeline

router = APIRouter(prefix="/api/documents", tags=["processing"])


def get_doc_owner(request: Request):
    from backend.main import require_user
    return require_user(request)


def _doc_exists(document_id):
    with db() as conn:
        row = conn.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Document not found")
        return dict(row)


@router.post("/{document_id}/process")
def process_document(document_id: int, user: dict = Depends(get_doc_owner)):
    doc = _doc_exists(document_id)
    if doc["status"] in ("processing",):
        raise HTTPException(status_code=409, detail="Document already processing")
    thread = threading.Thread(target=run_pipeline, args=(document_id,), daemon=True)
    thread.start()
    audit.log(actor=user["email"], action="process_start", entity="document", document_id=document_id,
              detail="AI processing pipeline started")
    return {"message": "Processing started in background", "document_id": document_id}


@router.get("/{document_id}/status")
def get_status(document_id: int, user: dict = Depends(get_doc_owner)):
    doc = _doc_exists(document_id)
    with db() as conn:
        stages = [dict(r) for r in conn.execute(
            "SELECT * FROM job_stages WHERE document_id=? ORDER BY id", (document_id,)).fetchall()]
        status_rows = conn.execute("SELECT key, value FROM job_status WHERE document_id=?", (document_id,)).fetchall()
    status_map = {r["key"]: r["value"] for r in status_rows}
    return {
        "id": doc["id"],
        "status": doc["status"],
        "stage": doc["stage"],
        "progress": doc["progress"],
        "error": doc["error"],
        "stages": stages,
        "ocr_confidence": doc["ocr_confidence"],
        "payload": status_map,
    }
