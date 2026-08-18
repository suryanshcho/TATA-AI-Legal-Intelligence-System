from fastapi import FastAPI, Depends, HTTPException, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.config import settings, BASE_DIR
from backend.database import init_db, db
from backend.auth import verify_password, make_token, parse_token, hash_password, now
from backend import audit
from backend.schemas import LoginRequest, UserUpdate, SettingsUpdate
from backend.api import documents, processing, clauses, rag, review, dashboard

app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router)
app.include_router(processing.router)
app.include_router(clauses.router)
app.include_router(rag.router)
app.include_router(review.router)
app.include_router(dashboard.router)


@app.on_event("startup")
def on_startup():
    init_db()
    from ai_workflows.rag_retrieval import build_knowledge_index
    build_knowledge_index()


def require_user(request: Request) -> dict:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    token = auth_header.split(" ", 1)[1]
    payload = parse_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload


@app.post("/api/auth/login")
def login(payload: LoginRequest, request: Request):
    with db() as conn:
        row = conn.execute("SELECT * FROM users WHERE email=?", (payload.email.strip().lower(),)).fetchone()
        if not row or not verify_password(payload.password, row["password_hash"]):
            audit.log(actor=payload.email, action="login_failed", entity="auth",
                      ip=request.client.host if request.client else None)
            raise HTTPException(status_code=401, detail="Invalid credentials")
        token = make_token(row["id"], row["email"], row["role"])
    audit.log(actor=row["email"], action="login", entity="auth",
              ip=request.client.host if request.client else None)
    return {"token": token, "user": {"id": row["id"], "email": row["email"], "name": row["name"],
                                     "role": row["role"], "business_unit": row["business_unit"]}}


@app.get("/api/auth/me")
def me(user: dict = Depends(require_user)):
    with db() as conn:
        row = conn.execute("SELECT * FROM users WHERE id=?", (user["user_id"],)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        return {"id": row["id"], "email": row["email"], "name": row["name"], "role": row["role"],
                "business_unit": row["business_unit"]}


@app.put("/api/account/profile")
def update_profile(payload: UserUpdate, user: dict = Depends(require_user)):
    with db() as conn:
        fields, params = [], []
        if payload.name is not None:
            fields.append("name=?"); params.append(payload.name)
        if payload.business_unit is not None:
            fields.append("business_unit=?"); params.append(payload.business_unit)
        if payload.role is not None:
            fields.append("role=?"); params.append(payload.role)
        if payload.password:
            fields.append("password_hash=?"); params.append(hash_password(payload.password))
        if fields:
            params.append(user["user_id"])
            conn.execute(f"UPDATE users SET {', '.join(fields)} WHERE id=?", params)
    audit.log(actor=user["email"], action="profile_update", entity="user")
    return {"message": "Profile updated"}


@app.put("/api/account/settings")
def update_settings(payload: SettingsUpdate, user: dict = Depends(require_user)):
    with db() as conn:
        for key, value in payload.dict(exclude_none=True).items():
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", (key, str(value)))
    audit.log(actor=user["email"], action="settings_update", entity="settings", detail=str(payload.dict(exclude_none=True)))
    return {"message": "Settings updated"}


@app.get("/api/account/settings")
def get_settings(user: dict = Depends(require_user)):
    with db() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
        return {r["key"]: r["value"] for r in rows}


@app.get("/api/audit")
def global_audit(user: dict = Depends(require_user)):
    return audit.fetch(limit=500)


@app.get("/api/health")
def health():
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION,
            "ai_mode": "gemini" if settings.GEMINI_API_KEY else "offline"}


FRONTEND_DIR = BASE_DIR / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/")
def index():
    return FileResponse(str(FRONTEND_DIR / "index.html"))
