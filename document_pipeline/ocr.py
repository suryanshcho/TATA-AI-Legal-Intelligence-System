import io
import logging
from pathlib import Path

from backend.config import settings

logger = logging.getLogger("ocr")


def extract_text(file_path: str, ext: str) -> dict:
    ext = ext.lower()
    try:
        if ext == ".pdf":
            return _pdf_text(file_path)
        if ext in (".docx", ".doc"):
            return _docx_text(file_path)
        if ext in (".png", ".jpg", ".jpeg"):
            return _image_ocr(file_path)
        if ext in (".txt", ".md", ".html"):
            content = Path(file_path).read_text(errors="replace")
            return {"text": content, "pages": 1, "confidence": 100.0, "engine": "plaintext", "warnings": []}
    except Exception as exc:
        logger.warning("Text extraction failed for %s: %s", file_path, exc)
        return {"text": "", "pages": 0, "confidence": 0.0, "engine": "failed", "warnings": [str(exc)]}
    return {"text": "", "pages": 0, "confidence": 0.0, "engine": "unsupported", "warnings": ["unsupported format"]}


def _pdf_text(file_path: str) -> dict:
    try:
        import fitz
    except ImportError:
        return {"text": "", "pages": 0, "confidence": 0.0, "engine": "missing-pymupdf",
                "warnings": ["pip install pymupdf for PDF support"]}
    doc = fitz.open(file_path)
    pages = []
    confidences = []
    for page in doc:
        txt = page.get_text().strip()
        pages.append(txt)
        confidences.append(100.0 if txt else 0.0)
    full = "\n\n".join(pages)
    avg_conf = sum(confidences) / len(confidences) if confidences else 0
    warnings = []
    if avg_conf < 60:
        warnings.append("Low text-layer confidence - scanned PDF likely, consider OCR")
    if not full.strip():
        ocr = _image_ocr_pdf(doc)
        if ocr["text"]:
            return ocr
    return {"text": full, "pages": len(pages), "confidence": round(avg_conf, 1), "engine": "pymupdf", "warnings": warnings}


def _image_ocr_pdf(doc):
    text = []
    confs = []
    for page in doc:
        pix = page.get_pixmap(dpi=200)
        img_bytes = pix.tobytes("png")
        res = _tesseract_ocr(img_bytes)
        text.append(res["text"])
        confs.append(res["confidence"])
    avg = sum(confs) / len(confs) if confs else 0
    return {"text": "\n\n".join(text), "pages": len(text), "confidence": round(avg, 1), "engine": "tesseract",
            "warnings": []}


def _docx_text(file_path: str) -> dict:
    try:
        import docx
    except ImportError:
        return {"text": "", "pages": 0, "confidence": 0.0, "engine": "missing-python-docx",
                "warnings": ["pip install python-docx for DOCX support"]}
    d = docx.Document(file_path)
    paras = [p.text for p in d.paragraphs if p.text.strip()]
    for table in d.tables:
        for row in table.rows:
            paras.append(" | ".join(cell.text for cell in row.cells))
    return {"text": "\n".join(paras), "pages": 1, "confidence": 100.0, "engine": "python-docx", "warnings": []}


def _image_ocr(file_path: str) -> dict:
    img_bytes = Path(file_path).read_bytes()
    return _tesseract_ocr(img_bytes)


def _tesseract_ocr(img_bytes: bytes) -> dict:
    try:
        from PIL import Image
        import pytesseract
    except ImportError:
        return {"text": "", "pages": 1, "confidence": 0.0, "engine": "missing-tesseract",
                "warnings": ["pip install pytesseract pillow and tesseract OCR binary"]}
    try:
        img = Image.open(io.BytesIO(img_bytes))
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        words = [w for w in data["text"] if w.strip()]
        confs = [float(c) for c, w in zip(data["conf"], data["text"]) if w.strip()]
        text = "\n".join(line for line in data["text"] if line.strip())
        avg_conf = sum(confs) / len(confs) if confs else 0.0
        return {"text": text, "pages": 1, "confidence": round(avg_conf, 1), "engine": "tesseract", "warnings": []}
    except Exception as exc:
        return {"text": "", "pages": 1, "confidence": 0.0, "engine": "tesseract-error", "warnings": [str(exc)]}
