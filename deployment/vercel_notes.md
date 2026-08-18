# Vercel Notes (frontend separation)

The frontend works out of the box served by FastAPI (single deployment, simplest option).
If you want the UI on **Vercel** and the API on **Render/Railway**, do this:

## Option 1 — Proxy via Vercel rewrites (easiest, recommended)

1. Create `vercel.json` in the repo root:

```json
{
  "rewrites": [
    { "source": "/api/(.*)", "destination": "https://your-api.onrender.com/api/$1" },
    { "source": "/(.*)", "destination": "/frontend/$1" }
  ]
}
```

2. Move `frontend/` to the repo root if needed, or adjust the second rewrite.
3. Vercel → Import repo → Framework preset **Other** → Deploy.
4. In `frontend/js/app.js`, the API base is `/api` — the rewrite forwards it to your backend.

> The `/api/health` endpoint also doubles as an uptime check.

## Option 2 — Serve frontend from Vercel, API absolute URL

1. In `frontend/js/app.js`, change the fetch base to your API origin, e.g.
   `const API_BASE = "https://your-api.onrender.com/api";`
2. Set `CORS_ORIGINS` on the backend to your Vercel domain (e.g. `https://tata-legal.vercel.app`).
3. Deploy `frontend/` as a static site on Vercel.

## Caveats

- Authentication is token-based (Authorization header) — no cookies needed, so cross-origin works once CORS is set.
- If you run the **backend** serverless on Vercel (functions), background threads and local SQLite won't work — keep the backend on Render/Railway/Colab instead.
- Keep `GEMINI_API_KEY` on the backend environment, never in the frontend.
