import uuid
from pathlib import Path

from backend.config import settings, UPLOAD_DIR


def save_upload(filename: str, content: bytes) -> dict:
    ext = Path(filename).suffix.lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file type '{ext}'")
    if len(content) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise ValueError(f"File exceeds {settings.MAX_UPLOAD_MB} MB limit")
    safe_name = f"{uuid.uuid4().hex}{ext}"
    path = UPLOAD_DIR / safe_name
    path.write_bytes(content)
    return {"path": str(path), "size": len(content), "ext": ext, "safe_name": safe_name}


def get_path(relative_path: str) -> Path:
    return UPLOAD_DIR / Path(relative_path).name


def delete_file(relative_path: str):
    try:
        p = get_path(relative_path)
        if p.exists():
            p.unlink()
    except Exception:
        pass
