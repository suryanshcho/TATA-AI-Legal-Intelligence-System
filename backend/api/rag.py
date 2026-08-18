from fastapi import APIRouter, Depends, Request

from backend.database import db
from backend.schemas import RetrievalQuery
from ai_workflows.rag_retrieval import retrieve, load_all_knowledge, build_knowledge_index

router = APIRouter(prefix="/api/rag", tags=["rag"])


def get_user(request: Request):
    from backend.main import require_user
    return require_user(request)


@router.get("/index")
def index_info(user: dict = Depends(get_user)):
    count = build_knowledge_index()
    return {"indexed_items": count, "embedding_mode": "tfidf", "note": "Approved clause library + policy references"}


@router.post("/retrieve")
def retrieve_context(payload: RetrievalQuery, user: dict = Depends(get_user)):
    results = retrieve(payload.query, payload.doc_type, payload.top_k)
    return {"query": payload.query, "results": results}


@router.get("/knowledge")
def knowledge_base(user: dict = Depends(get_user)):
    items = load_all_knowledge()
    return {"items": items, "total": len(items)}
