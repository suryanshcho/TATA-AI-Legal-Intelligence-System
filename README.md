# TATA Group — AI Legal Document Intelligence System

> Review, analyze and manage legal documents with AI-powered risk intelligence. A governed, audit-ready document-intelligence pipeline that takes legal documents from **upload → OCR → parsing → clause extraction → RAG retrieval → legal reasoning → summarization → human approval**.

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10+-007ACC) ![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688) ![Frontend](https://img.shields.io/badge/Frontend-HTML%2FCSS%2FJS-E34F26) ![AI](https://img.shields.io/badge/AI-Gemini%20%7C%20Offline%20Engine-00E5FF) ![Status](https://img.shields.io/badge/Status-Demo%20Ready-00FF9D)

</div>

---

## 1. What This System Does

The AI Legal Document Intelligence System converts uploaded legal documents into **structured legal intelligence** — extracted clauses, obligation maps, grounded summaries, and explainable risk flags — while keeping **human approval** and **audit trails** at the center.

### The Core Workflow (End-to-End)

```
UPLOAD → OCR → PARSING → CLAUSE EXTRACTION → RAG RETRIEVAL → LEGAL REASONING → SUMMARIZATION → HUMAN REVIEW
   │       │        │            │                    │                  │                 │            │
  .pdf    scanned  sections  16+ clause types   approved clause       risk flags      executive     accept/
 .docx    → text   + tables  indemnity, liab,   library + policy     w/ rationale,   summary +      edit/
 .txt     conf%              termination...     references           severity, evi-  obligation     escalate/
  ...                                      dence, confidence        map             reject
```

Every stage is recorded as a **processing job stage** with status and detail, and every reviewer action is written to an **audit log**.

### Key Features

| Feature | Detail |
|---|---|
| **Document Intake** | PDF, DOCX, TXT, MD, PNG/JPG uploads with business metadata (type, unit, counterparty, jurisdiction, confidentiality, priority) |
| **OCR & Parsing** | Text extraction with page-level confidence; scanned PDF → OCR; section/heading detection |
| **Clause Extraction** | 20+ clause types detected and normalized (indemnity, liability caps, termination, renewal, data protection, governing law, non-compete, force majeure, IP, SLAs…) |
| **RAG Knowledge Layer** | Retrieves approved clause-library and policy references to ground reasoning (TF-IDF vector index, no external DB needed) |
| **Risk Flagging** | Every flag includes **category, severity, rationale, evidence, confidence, recommendation** and reviewer state |
| **Summarization** | Review-ready contract summary + obligation map + missing-clauses list, marked *SYSTEM-GENERATED · PENDING LEGAL REVIEW* |
| **Human Approval** | Accept / Edit / Escalate / Reject / Comment per document and per risk flag |
| **Audit Trail** | Every upload, pipeline stage, model call, retrieval reference, review action and login is logged |
| **Dashboard & Ops** | KPIs, processing pipeline stats, AI accuracy, risk category matrix, recent documents |
| **Dual AI Mode** | Real **Gemini** when a free API key is present, otherwise a built-in **offline rule engine** — the demo works with *zero* API cost |

---

## 2. Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python · FastAPI · SQLite (zero-config database) |
| Frontend | Vanilla HTML / CSS / JavaScript — dark **robotic/HUD theme**, fully responsive |
| OCR | PyMuPDF (PDF text layer) + optional Tesseract/PaddleOCR for scanned images |
| Vector / Retrieval | Built-in TF-IDF + cosine retrieval over the approved knowledge base (Chroma optional) |
| LLM | Google Gemini (optional, free key) with a JSON-schema-constrained prompt layer |
| Auth | HMAC-signed tokens, SHA-256 password hashing, role-aware endpoints |
| Deployment | Anywhere uvicorn runs (Render, Railway, Hugging Face Spaces, Colab, Vercel w/ serverless) |

---

## 3. Repository Structure

```
tata-ai-legal-document-intelligence-system/
├── README.md                     ← you are here
├── .env.example                  ← copy to .env (never commit .env)
├── .gitignore
├── requirements.txt
├── run.py                        ← python run.py  (start server)
├── seed_demo.py                  ← optional: ingest + analyze sample contracts
│
├── backend/                      ← FastAPI application
│   ├── main.py                   ← app, auth, account, settings, audit, static hosting
│   ├── config.py                 ← settings from environment / .env
│   ├── database.py               ← SQLite schema + reentrant connection context
│   ├── auth.py                   ← password hashing + signed token helpers
│   ├── storage.py                ← upload validation & file storage
│   ├── audit.py                  ← audit logging helpers
│   ├── schemas.py                ← Pydantic request models
│   └── api/
│       ├── documents.py          ← upload / list / get / delete
│       ├── processing.py         ← trigger pipeline, job status
│       ├── clauses.py            ← clauses / risks / summary / document audit
│       ├── rag.py                ← knowledge index + retrieval
│       ├── review.py             ← human approval actions
│       └── dashboard.py          ← operations KPIs
│
├── document_pipeline/            ← the processing pipeline stages
│   ├── pipeline.py               ← orchestrator (runs the job through all stages)
│   ├── ocr.py                    ← text extraction (PDF/DOCX/images/plaintext)
│   ├── parsing.py                ← heading/section detection
│   ├── clause_extraction.py      ← 20+ clause-type extraction + missing-clause checks
│   ├── normalization.py          ← parties, dates, governing law, amounts, term
│   └── quality_checks.py         ← readability / OCR confidence scoring
│
├── ai_workflows/                 ← the AI layer
│   ├── llm_client.py             ← Gemini client (auto-detect, graceful fallback)
│   ├── offline_engine.py         ← rule-based risk engine (works without API key)
│   ├── rag_retrieval.py          ← knowledge index build + TF-IDF retrieval
│   ├── legal_reasoning.py        ← risk flag generation (LLM or offline)
│   ├── summarization.py          ← contract summary generation
│   ├── prompt_templates.py       ← Gemini system/user prompts + schemas
│   └── output_schemas.py         ← JSON output schemas
│
├── data/                         ← knowledge assets
│   ├── sample_contracts/         ← 2 risky sample agreements for demos
│   ├── clause_library/           ← approved clause templates (20 items)
│   ├── policy_references/        ← Tata policy guidance (4 items)
│   ├── risk_taxonomy.csv         ← 40 risk patterns → severity + rationale + action
│   └── sample_review_records.csv
│
├── frontend/                     ← robotic-themed responsive SPA
│   ├── index.html
│   ├── css/styles.css
│   └── js/app.js
│
├── docs/                         ← documentation (see section 8)
├── deployment/                   ← deployment runbooks (see section 9)
├── colab/
│   └── tata_legal_colab.ipynb    ← Google Colab notebook
├── tests/
│   └── test_pipeline.py          ← 5 end-to-end API tests (pytest)
└── uploads/                      ← uploaded files (git-ignored)
```

---

## 4. Setup (VS Code / Local)

### Prerequisites
- Python 3.10+ ([python.org](https://python.org))
- VS Code with the **Python** extension (optional)

### Step 1 — Get the code
```bash
git clone <your-github-repo-url> tata-ai-legal-document-intelligence-system
cd tata-ai-legal-document-intelligence-system
```

### Step 2 — Create a virtual environment
```bash
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
```

### Step 3 — Install dependencies
```bash
pip install -r requirements.txt
```
> Optional extras: `pip install pytesseract pillow` + [Tesseract OCR binary](https://github.com/tesseract-ocr/tesseract) for scanned-image OCR, and `pip install python-docx` for DOCX files. The demo works without these.

### Step 4 — Environment
```bash
cp .env.example .env      # then edit .env if needed
```
You can run the system **without any API key** — the offline AI engine kicks in automatically (`AI_MODE=auto`).

**Optional:** add a free Gemini key from <https://aistudio.google.com/apikey>:
```
GEMINI_API_KEY=your_free_key_here
```

### Step 5 — Run
```bash
python run.py
```
Open **http://localhost:8000** in your browser.

**Demo login:** `admin@tata.com` / `tata123`

### Step 6 — (Optional) Pre-load sample contracts
```bash
python seed_demo.py
```
This ingests the two sample agreements and runs the full AI pipeline on them so the dashboard has data immediately.

---

## 5. Demo Walkthrough (2 minutes)

1. **Login** with `admin@tata.com` / `tata123`.
2. Open **Dashboard** → see KPIs, pipeline stats, risk matrix.
3. Go to **Upload Document** → drag `data/sample_contracts/vendor_agreement_sample.txt` (or upload any PDF/DOCX/TXT) → choose **Vendor Agreement** → **TRANSMIT DOCUMENT**. Processing starts automatically.
4. Open **Processing** → watch the pipeline stages (OCR → Parsing → Clause Extraction → RAG → Reasoning → Risk Flagging → Summarization) complete live.
5. Open **Review & Risk** → read the AI summary, the extracted clauses, and the risk flags. Each flag shows severity, rationale, evidence, confidence and recommended action.
6. Click **APPROVE** (or Escalate / Reject / Comment) → the decision is recorded in the audit trail.
7. Open **Audit History** → every action is traceable.

---

## 6. API Overview

Interactive docs are available at **http://localhost:8000/docs** once the server runs.

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/auth/login` | Login, returns bearer token |
| GET | `/api/auth/me` | Current user |
| PUT | `/api/account/profile` | Update profile / password |
| GET/PUT | `/api/account/settings` | AI mode, model, routing settings |
| GET | `/api/health` | Health + active AI mode |
| POST | `/api/documents/upload` | Upload document (multipart) + metadata |
| GET | `/api/documents` | List documents (filters: status, risk, doc_type) |
| GET | `/api/documents/{id}` | Document detail + stages |
| DELETE | `/api/documents/{id}` | Delete document + analysis |
| POST | `/api/documents/{id}/process` | Start AI pipeline (async) |
| GET | `/api/documents/{id}/status` | Pipeline stage progress |
| GET | `/api/documents/{id}/clauses` | Extracted clauses |
| GET | `/api/documents/{id}/risks` | Risk flags |
| GET | `/api/documents/{id}/summary` | AI summary |
| GET | `/api/documents/{id}/audit` | Per-document audit trail |
| POST | `/api/documents/{id}/review` | Approve / Edit / Escalate / Reject / Comment |
| POST | `/api/rag/retrieve` | Retrieval query against knowledge base |
| GET | `/api/rag/knowledge` | List knowledge base |
| GET | `/api/audit` | Global audit log |

Full API details, payloads and examples → `docs/api_documentation.md`.

---

## 7. AI Workflow Details

### How risk flags are generated (offline mode)
1. Extracted clauses are compared against **40 patterns** in `data/risk_taxonomy.csv` (each with severity, rationale, recommendation, confidence).
2. Missing expected clauses are detected per document type.
3. RAG retrieval pulls approved clause-library/policy context that is exposed alongside flags for reviewer validation.
4. In **Gemini mode**, the same evidence (clauses + retrieved context) is passed to a constrained prompt that must return valid JSON flags — the offline engine is the safe fallback.

### RAG knowledge base
- `data/clause_library/clause_library.json` — 20 approved clause templates (indemnity, liability, DPDP data protection, arbitration in India, SLAs…).
- `data/policy_references/policy_references.json` — 4 policy references (procurement compliance, data protection, AI governance, risk-flag guidance).
- Retrieval uses a built-in TF-IDF + cosine index (pure Python, no external services). A Chroma/Qdrant vector DB can be swapped in — see `docs/architecture.md`.

---

## 8. Documentation Index (`docs/`)

| File | Contents |
|---|---|
| `architecture.md` | System architecture, data model, pipeline design, extensibility |
| `api_documentation.md` | Every endpoint: params, request/response examples |
| `security_notes.md` | Auth, storage, secrets, AI governance, risk controls |
| `demo_script.md` | Narrated demo + sample data expected outputs |

---

## 9. Deployment (`deployment/`)

| File | Contents |
|---|---|
| `environment_setup.md` | Env vars, production hardening, database |
| `backend_deployment.md` | Deploy on Render / Railway / Hugging Face Spaces / Colab |
| `vercel_notes.md` | Options to host the frontend + API separately |

**Quick start (Render, ~5 min):**
1. Push the repo to GitHub.
2. Create a new **Web Service** on [Render](https://render.com), connect the repo.
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
5. Add `.env` values in Render's environment panel (or leave blank for offline mode).
6. Open the assigned URL → done. Add it to `README.md` → Deployment link.

**Google Colab:** open `colab/tata_legal_colab.ipynb` and run the cells — it installs dependencies, starts the server, and shows you a `ngrok` URL you can open in any browser.

---

## 10. Security Notes (summary)

- Passwords are SHA-256 peppered-hashed; sessions are HMAC-signed tokens with expiry.
- API keys live only in `.env` / environment variables — never committed.
- Uploads are validated by extension and size; files stored outside the web root.
- AI outputs are advisory and always carry a **PENDING LEGAL REVIEW** state until a human approves.
- Full audit trail of actions; sensitive document content is not returned in API errors.
- Read the full notes → `docs/security_notes.md`.

---

## 11. Testing

```bash
python -m pytest tests/ -v
```
Covers login, upload → process → clauses → risks → summary → review → audit, RAG retrieval, dashboard, and auth rejection.

---

## 12. Roadmap

- [ ] Swap in a real vector DB (Chroma/Qdrant) for dense retrieval
- [ ] Multi-user roles with per-document access control
- [ ] Obligation monitoring with deadline tracking
- [ ] Negotiation playbooks + clause deviation comparison across vendors
- [ ] Export review reports (PDF/DOCX) and e-signature integration

---

## 13. License & Credits

Built for the Tata Group legal / compliance technology initiative. Sample contracts are fictional and provided for demonstration only. The system is advisory — all outputs require review by qualified legal professionals.

**Team:** Product · Legal · Compliance · Frontend · Backend · AI · Data · QA · Security · Docs
