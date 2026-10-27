# RecallOS Deployment Guide

This document details the configuration and deployment steps for RecallOS on Render (Backend & PostgreSQL) and Vercel/Render (Frontend).

---

## 1. Environment Variables

### Backend (`.env` on Render Web Service)

| Variable | Description | Example / Default |
| :--- | :--- | :--- |
| `ENV` | Application environment (`development` or `production`) | `production` |
| `DATABASE_URL` | PostgreSQL connection string (psycopg2-compatible) | `postgresql://user:pass@ep-xyz.region.aws.neon.tech/neondb?sslmode=require` |
| `JWT_SECRET` | Secret key for JWT authentication (minimum 32 characters) | `min-32-chars-cryptographically-secure-random-secret` |
| `JWT_EXPIRE_MINUTES`| Expiration window for access tokens (in minutes) | `1440` (24 hours) |
| `GEMINI_API_KEY` | Google AI Studio Gemini API Key | `AIzaSy...` |
| `GEMINI_MODEL` | Gemini model name | `gemini-1.5-flash` |
| `ALLOWED_ORIGINS` | Comma-separated list of client origins (no wildcards in production) | `https://recallos.onrender.com,https://recallos.vercel.app` |
| `MAX_UPLOAD_MB` | Maximum allowed file upload size in MB | `10` |
| `MAX_VISION_PAGES` | Maximum pages processed for scanned PDFs in vision mode | `32` |
| `DAILY_CARD_LIMIT` | Default daily review queue limit | `50` |
| `ENABLE_DUEL` | Feature flag reserved for planned multiplayer quiz duel (keep disabled) | `false` |

---

## 2. Backend Deployment on Render

### Runtime & Build Configuration
RecallOS uses standard Python packages without external C-binary system dependencies:
- **Build Command:**
  ```bash
  pip install -r backend/requirements.txt && alembic -c backend/alembic.ini upgrade head
  ```
- **Start Command:**
  ```bash
  uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1
  ```
  *(Note: Single worker is recommended for in-memory WebSocket room state and sliding-window rate limiters).*

### Database Migrations
Migrations run automatically on build via `alembic upgrade head`. To manually apply migrations:
```bash
cd backend
alembic upgrade head
```

---

## 3. Scanned PDF & Vision Fallback Notes

- **Zero System Dependencies:** Scanned PDF chunking utilizes `pypdf.PdfWriter` completely in memory. No `poppler-utils` or `tesseract-ocr` packages are required on Render's slim Linux container.
- **Rate Limits & Cooldowns:** Multimodal calls to Gemini require rate-limit handling. RecallOS enforces a 6.0-second cooldown between vision chunks and caps jobs at `MAX_VISION_PAGES` (default 32 pages / 8 chunks).

---

## 4. Frontend Deployment (Render Static Site / Vercel)

- **Root Directory:** `frontend`
- **Build Command:** `npm run build`
- **Publish Directory:** `dist`
- **Environment Variables:**
  - `VITE_API_URL`: Backend public URL (e.g. `https://recallos-api.onrender.com`)
  - `VITE_WS_URL`: Backend WebSocket URL (e.g. `wss://recallos-api.onrender.com`)
