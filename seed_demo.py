from pathlib import Path

import fitz
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from backend.database import init_db, db
from backend.auth import hash_password, make_token
from backend.config import settings


def demo_seed():
    init_db()
    from ai_workflows.rag_retrieval import build_knowledge_index
    n = build_knowledge_index()
    print(f"Knowledge index built: {n} items")

    samples = list((ROOT / "data" / "sample_contracts").glob("*.txt"))
    from backend import storage
    from document_pipeline.pipeline import run_pipeline

    for path in samples:
        with db() as conn:
            row = conn.execute("SELECT id FROM documents WHERE original_name=?", (path.name,)).fetchone()
        if row:
            print(f"  already exists: {path.name}")
            continue
        saved = storage.save_upload(path.name, path.read_bytes())
        with db() as conn:
            cursor = conn.execute(
                "INSERT INTO documents (filename, original_name, file_type, doc_type, business_unit, "
                "counterparty, jurisdiction, confidentiality, review_priority, size_bytes, owner_email, "
                "status, stage) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (saved["path"], path.name, ".txt", "Vendor Agreement" if "vendor" in path.name else "Master Services Agreement",
                 "Legal", "NovaCloud / Omega", "India / USA", "Confidential", "High",
                 path.stat().st_size, "admin@tata.com", "uploaded", "uploaded"))
            doc_id = cursor.lastrowid
        print(f"Seeding: {path.name} (id={doc_id})")
        run_pipeline(doc_id)

    with db() as conn:
        docs = conn.execute("SELECT id, original_name, status FROM documents ORDER BY id").fetchall()
        for d in docs:
            print(f"  doc {d['id']}: {d['original_name']} -> {d['status']}")


if __name__ == "__main__":
    demo_seed()
