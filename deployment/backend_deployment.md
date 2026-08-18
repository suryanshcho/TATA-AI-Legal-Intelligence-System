# Backend Deployment

The backend is a standard FastAPI app — it runs anywhere uvicorn runs. Pick one:

---

## Option A — Render (recommended, free tier)

1. Push the repo to GitHub.
2. [render.com](https://render.com) → **New → Web Service** → connect repo.
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
5. Environment → add variables from `.env.example` (you can leave `GEMINI_API_KEY` empty for offline mode).
6. Deploy → Render gives you `https://<name>.onrender.com`.
7. Put that URL in `README.md` → Deployment link.

> Note: on the free tier the app sleeps after inactivity; it wakes on request.

## Option B — Railway

1. New Project → Deploy from GitHub repo.
2. Railway auto-detects Python. Add a start command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
3. Add env vars under **Variables**.
4. Get a public URL under **Settings → Networking → Generate Domain**.

## Option C — Hugging Face Spaces (free, Python)

1. Create a **Docker/Python** Space on huggingface.co → connect GitHub.
2. Space Dockerfile (SDK=gradio not required — expose port 7860):

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
EXPOSE 7860
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "7860"]
```

3. Add secrets (`GEMINI_API_KEY`, etc.) under **Settings → Secrets**.

## Option D — Google Colab (quick demo)

Run `colab/tata_legal_colab.ipynb` → it starts the server and prints a public **ngrok** URL.

---

## Frontend hosting note

The frontend is plain HTML/CSS/JS and is **served by FastAPI itself**, so a single deployment is enough. If you prefer to split it (e.g. Vercel hosting the static files pointing at a Render API), see `vercel_notes.md`. CORS is already configured via `CORS_ORIGINS`.
