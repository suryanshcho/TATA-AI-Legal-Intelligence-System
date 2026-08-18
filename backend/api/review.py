from fastapi import APIRouter, Depends, HTTPException, Request

from backend import audit
from backend.auth import now
from backend.database import db
from backend.schemas import ReviewAction

router = APIRouter(prefix="/api/documents", tags=["review"])


def get_user(request: Request):
    from backend.main import require_user
    return require_user(request)


@router.post("/{document_id}/review")
def review_action(document_id: int, payload: ReviewAction, user: dict = Depends(get_user)):
    with db() as conn:
        row = conn.execute("SELECT id FROM documents WHERE id=?", (document_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Document not found")

        if payload.risk_id:
            risk = conn.execute("SELECT * FROM risk_flags WHERE id=? AND document_id=?", (payload.risk_id, document_id)).fetchone()
            if not risk:
                raise HTTPException(status_code=404, detail="Risk flag not found")
            conn.execute(
                "UPDATE risk_flags SET status=?, reviewer_action=?, reviewer_note=?, reviewed_by=?, reviewed_at=? WHERE id=?",
                (payload.action, payload.action, payload.note, user["email"], now(), payload.risk_id))

        if payload.action == "approve":
            conn.execute("UPDATE documents SET status='approved', updated_at=? WHERE id=?", (now(), document_id))
            conn.execute("UPDATE summaries SET approval_status='approved', approved_by=?, approved_at=? WHERE document_id=?",
                         (user["email"], now(), document_id))
            open_risks = conn.execute(
                "SELECT COUNT(*) c FROM risk_flags WHERE document_id=? AND status='open'", (document_id,)).fetchone()["c"]
            if open_risks == 0:
                conn.execute("UPDATE documents SET status='completed' WHERE id=?", (document_id,))
        elif payload.action == "reject":
            conn.execute("UPDATE documents SET status='rejected', updated_at=? WHERE id=?", (now(), document_id))
            conn.execute("UPDATE summaries SET approval_status='rejected' WHERE document_id=?", (document_id,))
        elif payload.action == "escalate":
            conn.execute("UPDATE documents SET status='escalated', updated_at=? WHERE id=?", (now(), document_id))
            conn.execute("UPDATE summaries SET approval_status='escalated' WHERE document_id=?", (document_id,))
        elif payload.action == "edit" and payload.edited_summary:
            conn.execute(
                "UPDATE summaries SET content=?, approval_status='edited' WHERE document_id=?",
                (payload.edited_summary, document_id))
        elif payload.action == "comment":
            conn.execute("UPDATE documents SET updated_at=? WHERE id=?", (now(), document_id))

    audit.log(actor=user["email"], action=f"review_{payload.action}", entity="review", document_id=document_id,
              detail=payload.note or f"risk_id={payload.risk_id}")
    return {"message": f"Review action '{payload.action}' recorded", "document_id": document_id}
