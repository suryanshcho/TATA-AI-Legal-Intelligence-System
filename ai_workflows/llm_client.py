import json
import logging

from backend.config import settings
from backend.database import db

logger = logging.getLogger("llm")


class LLMClient:
    def __init__(self):
        self.mode = self._resolve_mode()
        self.model = settings.GEMINI_MODEL
        self._client = None
        if self.mode == "gemini":
            try:
                import google.generativeai as genai
                genai.configure(api_key=settings.GEMINI_API_KEY)
                self._client = genai
            except Exception as exc:
                logger.warning("Gemini init failed (%s) - falling back to offline engine", exc)
                self.mode = "offline"

    def _resolve_mode(self):
        mode = settings.AI_MODE
        with db() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key='ai_mode'").fetchone()
            if row:
                mode = row["value"]
        if mode == "offline":
            return "offline"
        if mode == "gemini":
            return "gemini" if settings.GEMINI_API_KEY else "offline"
        return "gemini" if settings.GEMINI_API_KEY else "offline"

    def available(self):
        return self.mode == "gemini"

    def generate(self, system_prompt: str, user_prompt: str, json_mode: bool = True, temperature: float = 0.2):
        if self.mode != "gemini" or self._client is None:
            raise RuntimeError("Gemini unavailable - use offline engine")
        try:
            model = self._client.GenerativeModel(
                self.model,
                system_instruction=system_prompt,
            )
            response = model.generate_content(
                user_prompt,
                generation_config={
                    "temperature": temperature,
                    "response_mime_type": "application/json" if json_mode else "text/plain",
                },
            )
            return self._parse_response(response.text, json_mode)
        except Exception as exc:
            logger.warning("Gemini call failed: %s", exc)
            raise

    def _parse_response(self, text, json_mode):
        if not json_mode:
            return text.strip()
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start, end = text.find("["), text.rfind("]")
            if start == -1:
                start, end = text.find("{"), text.rfind("}")
            if start != -1 and end != -1:
                try:
                    return json.loads(text[start:end + 1])
                except Exception:
                    pass
            return {"error": "unparseable", "raw": text[:2000]}
