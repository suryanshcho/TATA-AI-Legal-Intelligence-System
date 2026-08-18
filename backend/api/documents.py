import threading
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request

from backend import audit, storage
from backend.auth import now
from backend.database import db
from backend.schemas import DocumentCreate

router = APIRouter(prefix="/api/documents", tags=["documents"])


def get_doc_owner(request: Request):
    from backend.main import require_user
    return require_user(request)


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    doc_type: str = Form("Contract"),
    business_unit: str = Form("Corporate"),
    counterparty: str = Form(""),
    jurisdiction: str = Form(""),
    confidentiality: str = Form("Confidential"),
    review_priority: str = Form("Normal"),
    user: dict = Depends(get_doc_owner),
):
    content = await file.read()
    try:
        saved = storage.save_upload(file.filename, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    with db() as conn:
        cursor = conn.execute(
            "INSERT INTO documents (filename, original_name, file_type, doc_type, business_unit, counterparty, "
            "jurisdiction, confidentiality, review_priority, size_bytes, owner_id, owner_email, status, stage) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (saved["safe_name"], file.filename, saved["ext"], doc_type, business_unit, counterparty,
             jurisdiction, confidentiality, review_priority, saved["size"], user["user_id"], user["email"],
             "uploaded", "uploaded"),
        )
        doc_id = cursor.lastrowid
    audit.log(actor=user["email"], action="document_upload", entity="document", document_id=doc_id,
              detail=f"Uploaded {file.filename} ({saved['size']} bytes) type={doc_type}")
    return {"id": doc_id, "message": "Document uploaded. Use POST /api/documents/{id}/process to start AI processing."}


@router.get("")
def list_documents(status: str = None, risk: str = None, doc_type: str = None, user: dict = Depends(get_doc_owner)):
    with db() as conn:
        sql = "SELECT * FROM documents"
        where, params = [], []
        if status and status != "All":
            where.append("status=?")
            params.append(status.lower())
        if doc_type and doc_type != "All":
            where.append("doc_type=?")
            params.append(doc_type)
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY id DESC"
        rows = conn.execute(sql, params).fetchall()
        docs = [dict(r) for r in rows]
    for d in docs:
        d["high_risk_count"] = _risk_count(d["id"])
    if risk and risk != "All":
        if risk == "High":
            docs = [d for d in docs if d["high_risk_count"] > 0]
    return docs


@router.get("/{document_id}")
def get_document(document_id: int, user: dict = Depends(get_doc_owner)):
    with db() as conn:
        row = conn.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Document not found")
        doc = dict(row)
        doc["high_risk_count"] = _risk_count(document_id)
        doc["clause_count"] = conn.execute("SELECT COUNT(*) c FROM clauses WHERE document_id=?", (document_id,)).fetchone()["c"]
        doc["risk_count"] = conn.execute("SELECT COUNT(*) c FROM risk_flags WHERE document_id=?", (document_id,)).fetchone()["c"]
        doc["stages"] = [dict(r) for r in conn.execute(
            "SELECT * FROM job_stages WHERE document_id=? ORDER BY id", (document_id,)).fetchall()]
        doc["progress"] = doc["progress"] or 0
        return doc


@router.delete("/{document_id}")
def delete_document(document_id: int, user: dict = Depends(get_doc_owner)):
    with db() as conn:
        row = conn.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Document not found")
        storage.delete_file(row["filename"])
        for table in ("clauses", "risk_flags", "summaries", "job_stages", "job_status"):
            conn.execute(f"DELETE FROM {table} WHERE document_id=?", (document_id,))
        conn.execute("DELETE FROM documents WHERE id=?", (document_id,))
    audit.log(actor=user["email"], action="document_delete", entity="document", document_id=document_id,
              detail=f"Deleted {row['original_name']}")
    return {"message": "Document deleted"}


def _risk_count(document_id):
    with db() as conn:
        row = conn.execute(
            "SELECT COUNT(*) c FROM risk_flags WHERE document_id=? AND severity IN ('High','Critical')",
            (document_id,)).fetchone()
        return row["c"] if row else 0
