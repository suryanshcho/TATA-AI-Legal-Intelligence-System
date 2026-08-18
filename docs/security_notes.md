# Security Notes

## 1. Authentication & Sessions

- Passwords are hashed with **SHA-256 + a static pepper** (`backend/auth.py`). Do not store plaintext.
- Sessions are **HMAC-signed tokens** (payload + signature using `SECRET_KEY`) with an expiry (`TOKEN_TTL_HOURS`, default 24h). Signature verification uses constant-time comparison.
- **Production requirement**: change `SECRET_KEY` and `ADMIN_PASSWORD` in `.env`. Never use the defaults outside a local demo.

## 2. Secrets Management

- All secrets (Gemini API key, DB path, secret key, credentials) live in `.env` / environment variables, read by `backend/config.py`.
- `.env` is git-ignored. `.env.example` contains placeholders only.
- **Never** commit API keys, tokens, or `legal_intelligence.db` (contains user + audit data).

## 3. Document & Storage Security

- Uploads validated by extension whitelist (`ALLOWED_EXTENSIONS`) and size cap (`MAX_UPLOAD_MB`).
- Files are stored under `uploads/` with **random UUID names** (original filenames never used on disk), outside the static web root — not directly downloadable.
- Delete endpoints remove both DB records and files.

## 4. Legal Data Handling & AI Governance

- AI outputs are **advisory only**. Every summary is explicitly marked *SYSTEM-GENERATED · PENDING LEGAL REVIEW* until a human approves.
- In `AI_MODE=offline`, **no document text leaves the machine**. In Gemini mode, document text is sent to Google's API — ensure this is permitted by your data classification policy (the system labels documents `Confidential`/`Restricted`).
- Gemini prompts constrain the model to base flags on document evidence and retrieved approved references only; the offline engine is the automatic fallback on any error.

## 5. Audit & Traceability

- Every login (incl. failures), upload, pipeline stage, model call, retrieval reference, review action, and delete is logged to `audit_logs` with actor, action, entity, detail, IP and timestamp.
- Review actions record identity, timestamp, decision, and rationale.
- API error messages never echo raw document content.

## 6. Access Control

- Role field on users (`admin` / `reviewer`). Protected endpoints validate the bearer token on every request.
- Suggested production hardening: per-document access lists (business_unit scoping), row-level filtering in `backend/api/documents.py`, and HTTPS termination at the hosting layer.

## 7. Recommended Production Checklist

- [ ] Unique `SECRET_KEY`, strong admin credentials
- [ ] HTTPS enabled (Render/Railway provide by default)
- [ ] Database backups scheduled (`legal_intelligence.db` + `uploads/`)
- [ ] Monitor audit log for repeated `login_failed`
- [ ] Add per-business-unit data isolation if multi-tenant
- [ ] Keep model/OCR/DB credentials out of code and CI logs
