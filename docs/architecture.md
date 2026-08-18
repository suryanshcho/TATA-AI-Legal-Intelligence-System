# Architecture

## 1. Overview

The system is a **job-based document-intelligence pipeline**. Each uploaded document becomes a processing job that moves through independent, testable stages. The backend (FastAPI) orchestrates stages, stores structured outputs in SQLite, serves the frontend, and records every action in an audit log.

```
                        ┌────────────────────────────────────────────────────────────┐
                        │                        BROWSER                              │
                        │    HTML/CSS/JS robotic-themed SPA (frontend/)              │
                        └────────────────────────────┬───────────────────────────────┘
                                                     │ HTTP + Bearer token
                        ┌────────────────────────────▼───────────────────────────────┐
                        │                        FASTAPI (backend/)                  │
                        │   auth  │  documents  │  processing  │  review  │  audit   │
                        │   rag   │  dashboard  │  settings    │  account            │
                        └──────┬──────────────────┬───────────────────┬──────────────┘
                               │                  │                   │
                    ┌──────────▼───────┐   ┌──────▼────────────┐  ┌───▼─────────────┐
                    │ document_pipeline │   │  ai_workflows     │  │  SQLite storage │
                    │ ocr → parsing →   │   │ rag_retrieval     │  │ documents       │
                    │ clause → quality  │   │ legal_reasoning   │  │ clauses         │
                    │ (threaded job)    │   │ summarization     │  │ risk_flags      │
                    └──────────────────┘   │ offline_engine    │  │ summaries       │
                                           │ llm_client(Gemini)│  │ audit_logs      │
                                           └───────────────────┘  └─────────────────┘
```

## 2. Data Model

| Table | Purpose | Key fields |
|---|---|---|
| `users` | Operators & reviewers | email, role, business_unit, password_hash |
| `documents` | Document registry + job state | filename, doc_type, status, progress, stage, ocr_confidence, error |
| `job_stages` | Pipeline stage history | stage, status, started_at, finished_at, detail |
| `clauses` | Normalized extracted clauses | clause_type, clause_text, page, section, confidence |
| `risk_flags` | Explainable risk outputs | category, severity, rationale, evidence, recommendation, confidence, status, reviewer_* |
| `summaries` | Versioned AI summaries | content, obligation_map (JSON), approval_status, approved_by |
| `audit_logs` | Immutable audit trail | actor, action, entity, detail, ip, created_at |
| `settings` | Runtime config | ai_mode, llm_model, auto_review_routing |
| `knowledge_items` | (reserved) indexed knowledge | kind, title, category, content, source, approved |

Documents also carry business metadata: business_unit, counterparty, jurisdiction, confidentiality, review_priority.

## 3. Pipeline Stage Design

Each stage is an independent function returning structured data, persisted to SQLite:

1. **OCR (`document_pipeline/ocr.py`)** — PDF text layer via PyMuPDF; scanned pages fall back to Tesseract; DOCX via python-docx; plaintext direct. Returns text + page-level confidence + warnings.
2. **Parsing (`parsing.py`)** — detects headings/sections via regex patterns + a heading vocabulary; produces section blocks with char offsets.
3. **Clause Extraction (`clause_extraction.py`)** — searches 20+ clause types using keyword signatures; each hit yields label, snippet, page estimate, section, confidence. Also computes **missing expected clauses** per document type.
4. **Normalization (`normalization.py`)** — parties, dates, governing law, currency amounts, term length.
5. **RAG Retrieval (`ai_workflows/rag_retrieval.py`)** — builds a TF-IDF + cosine index over the clause library and policy references; ranks by relevance and document type.
6. **Legal Reasoning (`legal_reasoning.py`)** — Gemini (structured JSON) or offline rule engine → risk flags with severity/rationale/evidence/confidence.
7. **Risk Flagging** — flags routed with reviewer state; high/critical drive the document into `attention` status.
8. **Summarization (`summarization.py`)** — review-ready summary, obligation map, missing-clause list, always labeled PENDING LEGAL REVIEW.
9. **Human Review (`backend/api/review.py`)** — approve / edit / escalate / reject / comment; writes audit entries and updates approval state.

## 4. AI Mode Strategy

- `AI_MODE=auto` (default): use **Gemini** if `GEMINI_API_KEY` is set, otherwise the **offline engine**.
- The offline engine uses `data/risk_taxonomy.csv` (40 patterns) + missing-clause logic, so the product is fully functional with **no paid API**.
- Gemini prompts are constrained to return JSON matching `ai_workflows/output_schemas.py`; any failure gracefully falls back to the offline engine.

## 5. Retrieval & Knowledge Layer

- Knowledge assets: `data/clause_library/clause_library.json` (20 approved clauses) and `data/policy_references/policy_references.json` (4 policy refs).
- Index: pure-Python TF-IDF with cosine similarity (no external vector DB required).
- Swapping in a vector DB: replace `rag_retrieval.build_knowledge_index` / `retrieve` with a Chroma/Qdrant client embedding the same `content` fields (see `rag.py` API — the surface is already DB-agnostic).

## 6. Concurrency & Isolation

- Processing runs in a background thread per document (SQLite WAL mode + reentrant connection context handle nested transactions safely).
- Status polling is exposed via `GET /api/documents/{id}/status`; the frontend polls while a job is active.

## 7. Extensibility

- **New risk rules**: append rows to `data/risk_taxonomy.csv` (category, severity, regex pattern, rationale, recommendation, confidence, clause_type).
- **New clause types**: add an entry to `CLAUSE_DEFS` in `document_pipeline/clause_extraction.py`.
- **New knowledge**: add items to the clause library / policy JSON files.
- **New pipeline stage**: add a function + a `_stage(...)` call in `document_pipeline/pipeline.py`, and add its label to the frontend stage map in `frontend/js/app.js`.
