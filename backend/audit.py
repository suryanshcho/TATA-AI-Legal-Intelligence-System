from backend.database import db
from backend.auth import now


def log(actor, action, entity=None, document_id=None, detail=None, ip=None):
    with db() as conn:
        conn.execute(
            "INSERT INTO audit_logs (document_id, actor, action, entity, detail, ip) VALUES (?,?,?,?,?,?)",
            (document_id, actor, action, entity, detail, ip),
        )


def fetch(document_id=None, limit=200):
    with db() as conn:
        if document_id is not None:
            rows = conn.execute(
                "SELECT * FROM audit_logs WHERE document_id=? ORDER BY id DESC LIMIT ?",
                (document_id, limit),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]


def record_stage(document_id, stage, status, detail=None):
    with db() as conn:
        conn.execute(
            "INSERT INTO job_stages (document_id, stage, status, started_at, finished_at, detail) VALUES (?,?,?,?,?,?)",
            (document_id, stage, status, now(), now() if status == "done" else None, detail),
        )
        conn.execute("UPDATE documents SET stage=?, updated_at=? WHERE id=?", (stage, now(), document_id))
