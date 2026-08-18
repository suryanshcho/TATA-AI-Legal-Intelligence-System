import os
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ["AI_MODE"] = "offline"
os.environ["DB_PATH"] = str(ROOT / "test_intelligence.db")
os.environ["ADMIN_PASSWORD"] = "tata123"

from fastapi.testclient import TestClient

from backend.database import init_db, db
from backend.main import app

client = TestClient(app)
TOKEN = None


@pytest.fixture(scope="module", autouse=True)
def setup():
    init_db()
    res = client.post("/api/auth/login", json={"email": "admin@tata.com", "password": "tata123"})
    global TOKEN
    TOKEN = res.json()["token"]
    yield
    db_path = ROOT / "test_intelligence.db"
    for suffix in ("", "-wal", "-shm"):
        p = Path(str(db_path) + suffix)
        if p.exists():
            p.unlink()


def auth():
    return {"Authorization": f"Bearer {TOKEN}"}


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_upload_process_review_flow():
    sample = ROOT / "data" / "sample_contracts" / "vendor_agreement_sample.txt"
    with open(sample, "rb") as f:
        r = client.post(
            "/api/documents/upload",
            headers=auth(),
            files={"file": ("vendor_test.txt", f, "text/plain")},
            data={"doc_type": "Vendor Agreement", "business_unit": "Legal",
                  "counterparty": "NovaCloud", "jurisdiction": "USA"},
        )
    assert r.status_code == 200, r.text
    doc_id = r.json()["id"]

    r = client.post(f"/api/documents/{doc_id}/process", headers=auth())
    assert r.status_code == 200

    for _ in range(30):
        time.sleep(1)
        status = client.get(f"/api/documents/{doc_id}/status", headers=auth()).json()
        if status["status"] in ("attention", "completed", "approved", "failed"):
            break
    assert status["status"] in ("attention", "completed"), status

    clauses = client.get(f"/api/documents/{doc_id}/clauses", headers=auth()).json()
    assert len(clauses) > 5
    assert any(c["clause_type"] == "indemnity" for c in clauses)

    risks = client.get(f"/api/documents/{doc_id}/risks", headers=auth()).json()
    assert len(risks) >= 1
    for risk in risks:
        assert risk["category"]
        assert risk["severity"] in ("Low", "Medium", "High", "Critical")
        assert risk["rationale"]
        assert 0 <= risk["confidence"] <= 1

    summary = client.get(f"/api/documents/{doc_id}/summary", headers=auth()).json()
    assert summary["content"]

    r = client.post(f"/api/documents/{doc_id}/review", headers=auth(),
                    json={"action": "comment", "note": "checked"})
    assert r.status_code == 200

    audit = client.get(f"/api/documents/{doc_id}/audit", headers=auth()).json()
    assert any(a["action"] == "pipeline_complete" for a in audit)


def test_rag_retrieval():
    r = client.post("/api/rag/retrieve", headers=auth(),
                    json={"query": "vendor agreement indemnity liability", "top_k": 3})
    assert r.status_code == 200
    assert len(r.json()["results"]) >= 1


def test_dashboard():
    r = client.get("/api/dashboard", headers=auth())
    assert r.status_code == 200
    data = r.json()
    assert data["total_documents"] >= 1


def test_auth_rejected():
    r = client.get("/api/dashboard")
    assert r.status_code == 401
