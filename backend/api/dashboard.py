from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request

from backend.database import db

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def get_user(request: Request):
    from backend.main import require_user
    return require_user(request)


@router.get("")
def dashboard(user: dict = Depends(get_user)):
    with db() as conn:
        total = conn.execute("SELECT COUNT(*) c FROM documents").fetchone()["c"]
        completed = conn.execute("SELECT COUNT(*) c FROM documents WHERE status IN ('completed','approved')").fetchone()["c"]
        processing = conn.execute("SELECT COUNT(*) c FROM documents WHERE status='processing'").fetchone()["c"]
        pipeline = conn.execute("SELECT COUNT(*) c FROM documents WHERE status IN ('uploaded','processing')").fetchone()["c"]
        high_risk = conn.execute("SELECT COUNT(*) c FROM documents WHERE status='attention'").fetchone()["c"]
        attention = conn.execute("SELECT COUNT(*) c FROM risk_flags WHERE severity IN ('High','Critical') AND status='open'").fetchone()["c"]
        total_risks = conn.execute("SELECT COUNT(*) c FROM risk_flags").fetchone()["c"]
        avg_conf = conn.execute("SELECT AVG(confidence) c FROM risk_flags").fetchone()["c"] or 0

        recent = conn.execute("SELECT * FROM documents ORDER BY id DESC LIMIT 8").fetchall()

        avg_time = _avg_analysis_time(conn)
        recent_docs = []
        for r in recent:
            d = dict(r)
            d["high_risk_count"] = conn.execute(
                "SELECT COUNT(*) c FROM risk_flags WHERE document_id=? AND severity IN ('High','Critical')",
                (r["id"],)).fetchone()["c"]
            recent_docs.append(d)

        by_status = [dict(x) for x in conn.execute(
            "SELECT status, COUNT(*) c FROM documents GROUP BY status ORDER BY c DESC").fetchall()]
        risk_by_category = [dict(x) for x in conn.execute(
            "SELECT category, COUNT(*) c FROM risk_flags GROUP BY category ORDER BY c DESC LIMIT 8").fetchall()]

    completion = round((completed / total) * 100) if total else 0
    return {
        "total_documents": total,
        "completed": completed,
        "processing": processing,
        "in_pipeline": pipeline,
        "high_risk_docs": high_risk,
        "attention_required": attention,
        "completion_percent": completion,
        "avg_analysis_time_min": avg_time,
        "documents_in_queue": pipeline,
        "ai_accuracy": round(min(99, (avg_conf or 0.75) * 100), 1),
        "total_risks": total_risks,
        "recent_documents": recent_docs,
        "by_status": by_status,
        "risk_by_category": risk_by_category,
        "kpis": {
            "total": total, "completed": completed, "processing": processing,
            "pipeline": pipeline, "high_risk": high_risk, "attention": attention,
            "completion_percent": completion, "avg_time": avg_time, "queue": pipeline,
            "ai_accuracy": round(min(99, (avg_conf or 0.75) * 100), 1),
        },
    }


def _avg_analysis_time(conn):
    rows = conn.execute(
        "SELECT started_at, finished_at FROM job_stages WHERE stage='ocr' AND started_at IS NOT NULL ORDER BY id DESC LIMIT 10"
    ).fetchall()
    if not rows:
        return 1.4
    total = 0
    count = 0
    for r in rows:
        try:
            s = datetime.strptime(r["started_at"], "%Y-%m-%d %H:%M:%S")
            f = datetime.strptime(r["finished_at"] or r["started_at"], "%Y-%m-%d %H:%M:%S")
            total += max((f - s).total_seconds(), 5)
            count += 1
        except Exception:
            continue
    avg_sec = total / count if count else 45
    return round(avg_sec / 60, 1)
