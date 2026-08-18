# Environment Setup

## Local (VS Code)

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python run.py                    # -> http://localhost:8000
```

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `AI_MODE` | `auto` | `auto` / `gemini` / `offline` |
| `GEMINI_API_KEY` | (empty) | Free key from aistudio.google.com/apikey |
| `GEMINI_MODEL` | `gemini-1.5-flash` | Gemini model |
| `DB_PATH` | `legal_intelligence.db` | SQLite file |
| `SECRET_KEY` | demo value | **change in production** |
| `TOKEN_TTL_HOURS` | `24` | Session expiry |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | `admin@tata.com` / `tata123` | Default seeded admin |
| `MAX_UPLOAD_MB` | `25` | Upload size cap |
| `ALLOWED_EXTENSIONS` | `.pdf,.docx,...` | Upload whitelist |
| `TOP_K_RETRIEVAL` | `5` | RAG results per query |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins |

## Optional dependencies

| Package | Enables |
|---|---|
| `pytesseract` + `pillow` + Tesseract binary | OCR of scanned images / scanned PDFs |
| `python-docx` | DOCX parsing |
| `paddleocr` / `easyocr` | Higher-accuracy OCR (heavier) |

## Production hardening

1. Set unique `SECRET_KEY`, strong `ADMIN_PASSWORD`.
2. Set `CORS_ORIGINS` to your real domain.
3. Use a managed DB (Postgres) or keep nightly SQLite backups.
4. Terminate TLS at the host (Render/Railway give HTTPS automatically).
5. Add per-business-unit row filtering before multi-tenant use (see security_notes).
