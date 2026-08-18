# API Documentation

Base URL: `http://localhost:8000` (or your deployed URL). All endpoints except `/api/auth/login` and `/api/health` require:

```
Authorization: Bearer <token>
```

Interactive docs: `http://localhost:8000/docs`

---

## Authentication

### POST /api/auth/login
Login and receive a token.

```json
{ "email": "admin@tata.com", "password": "tata123" }
```
Response:
```json
{
  "token": "<jwt-like-signed-token>",
  "user": { "id": 1, "email": "admin@tata.com", "name": "Tata Legal Admin", "role": "admin", "business_unit": "Corporate" }
}
```

### GET /api/auth/me
Returns the current user.

### PUT /api/account/profile
Update profile. Body (all optional):
```json
{ "name": "New Name", "business_unit": "Legal", "role": "reviewer", "password": "newpass" }
```

### GET/PUT /api/account/settings
System settings:
```json
{ "ai_mode": "auto", "llm_model": "gemini-1.5-flash", "auto_review_routing": "high_risk" }
```
`ai_mode`: `auto` | `gemini` | `offline`.

### GET /api/health
```json
{ "status": "ok", "app": "TATA AI Legal Document Intelligence System", "version": "1.0.0", "ai_mode": "offline" }
```

---

## Documents

### POST /api/documents/upload
Multipart form:
- `file` (file) — required
- `doc_type` — e.g. `Vendor Agreement`
- `business_unit`, `counterparty`, `jurisdiction`, `confidentiality`, `review_priority`

```bash
curl -X POST http://localhost:8000/api/documents/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@data/sample_contracts/vendor_agreement_sample.txt" \
  -F "doc_type=Vendor Agreement" -F "business_unit=Legal"
```
Response: `{ "id": 1, "message": "Document uploaded..." }`

### GET /api/documents
List documents. Optional query filters: `status`, `risk`, `doc_type`. Each item includes `high_risk_count`.

### GET /api/documents/{id}
Document detail with `clause_count`, `risk_count`, `high_risk_count`, and `stages[]`.

### DELETE /api/documents/{id}
Deletes the document and all of its analysis.

---

## Processing

### POST /api/documents/{id}/process
Starts the AI pipeline in a background thread.
```json
{ "message": "Processing started in background", "document_id": 1 }
```

### GET /api/documents/{id}/status
```json
{
  "id": 1, "status": "attention", "stage": "review", "progress": 100,
  "stages": [ { "stage": "ocr", "status": "done", "detail": "engine=plaintext conf=100.0 pages=1" }, ... ],
  "ocr_confidence": 100.0,
  "payload": { "metadata": "...", "retrieval_context": "...", "quality": "..." }
}
```
`status` values: `uploaded` → `processing` → `attention` (high/critical flags) | `completed` → `approved` / `escalated` / `rejected` / `failed`.

---

## Insights

### GET /api/documents/{id}/clauses
```json
[
  { "id": 1, "clause_type": "indemnity", "label": "Indemnification",
    "clause_text": "...", "page": 1, "section": "5. INDEMNIFICATION",
    "confidence": 0.95 }
]
```

### GET /api/documents/{id}/risks
```json
[
  { "id": 1, "category": "Unilateral Indemnity", "severity": "High",
    "rationale": "Indemnity obligations appear one-sided...",
    "evidence": "5.1 Vendor shall indemnify...", "recommendation": "Request mutual indemnification...",
    "confidence": 0.8, "status": "open", "reviewer_action": "pending" }
]
```

### GET /api/documents/{id}/summary
```json
{
  "document_id": 1, "content": "SYSTEM-GENERATED SUMMARY - PENDING LEGAL REVIEW\n...",
  "obligation_map": [ { "clause": "Indemnification", "obligation": "...", "party": "both parties" } ],
  "missing_clauses": [], "approval_status": "pending"
}
```

### GET /api/documents/{id}/audit
Per-document audit trail.

---

## Review (Human Approval)

### POST /api/documents/{id}/review
Body:
```json
{ "action": "approve", "risk_id": null, "note": "Optional note" }
```
`action`: `approve` | `edit` | `escalate` | `reject` | `comment`
- `edit` also accepts `edited_summary` (saves a new version, sets `edited` state).
- Any action with `risk_id` updates that risk flag's reviewer state and note.
- `approve` marks the summary approved and completes the document (unless open risks remain → `completed`).

---

## RAG / Knowledge

### POST /api/rag/retrieve
```json
{ "query": "vendor agreement indemnity liability", "doc_type": "Vendor Agreement", "top_k": 5 }
```
Response `results[]`: title, category, kind, content, source, approved, score.

### GET /api/rag/knowledge
Lists the entire knowledge base (clause library + policy references).

### GET /api/rag/index
Returns indexed item count and embedding mode.

---

## Audit

### GET /api/audit
Global audit log (latest 500). Fields: `created_at`, `actor`, `action`, `entity`, `document_id`, `detail`.

---

## Errors

All errors return RFC-7807 style JSON: `{ "detail": "<message>" }`
- `401` — missing/invalid token
- `404` — document not found
- `400` — unsupported file type / file too large
- `409` — document already processing
