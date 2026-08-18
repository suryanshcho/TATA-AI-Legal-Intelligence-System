import json

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.database import db

router = APIRouter(prefix="/api/documents", tags=["insights"])


def get_doc_owner(request: Request):
    from backend.main import require_user
    return require_user(request)


@router.get("/{document_id}/clauses")
def list_clauses(document_id: int, user: dict = Depends(get_doc_owner)):
    _exists(document_id)
    from document_pipeline.clause_extraction import CLAUSE_DEFS
    with db() as conn:
        rows = conn.execute("SELECT * FROM clauses WHERE document_id=? ORDER BY id", (document_id,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["label"] = CLAUSE_DEFS.get(d["clause_type"], {}).get("label", d["clause_type"])
            out.append(d)
        return out


@router.get("/{document_id}/risks")
def list_risks(document_id: int, user: dict = Depends(get_doc_owner)):
    _exists(document_id)
    with db() as conn:
        rows = conn.execute("SELECT * FROM risk_flags WHERE document_id=? ORDER BY id", (document_id,)).fetchall()
        return [dict(r) for r in rows]


@router.get("/{document_id}/summary")
def get_summary(document_id: int, user: dict = Depends(get_doc_owner)):
    _exists(document_id)
    with db() as conn:
        row = conn.execute("SELECT * FROM summaries WHERE document_id=? ORDER BY version DESC LIMIT 1", (document_id,)).fetchone()
        if not row:
            return {"document_id": document_id, "content": "", "obligation_map": [], "missing_clauses": [],
                    "approval_status": "not_generated"}
        s = dict(row)
        s["obligation_map"] = json.loads(s["obligation_map"] or "[]")
        s["missing_clauses"] = json.loads(s["missing_clauses"] or "[]")
        return s


@router.get("/{document_id}/audit")
def document_audit(document_id: int, user: dict = Depends(get_doc_owner)):
    _exists(document_id)
    from backend import audit
    return audit.fetch(document_id=document_id)


def _exists(document_id):
    with db() as conn:
        row = conn.execute("SELECT id FROM documents WHERE id=?", (document_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Document not found")
