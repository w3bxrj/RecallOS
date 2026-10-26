# RecallOS Backend Deployment Guide (Render & Neon)

This guide walks through deploying the RecallOS FastAPI backend to **Render (Free Tier)** with **Neon PostgreSQL** in the **Singapore** region.

---

## 1. Prerequisites & Region Alignment

To minimize network round-trip latency between the application server and the database, **both Render and Neon must be created in the Singapore region**:
- **Render Region:** `singapore`
- **Neon Region:** `ap-southeast-1` (Singapore)

---

## 2. Step 1: Create Neon PostgreSQL Database

1. Log in to [Neon Console](https://console.neon.tech/).
2. Create a new project named `recallos`.
3. Choose region: **Asia Pacific (Singapore) / `ap-southeast-1`**.
4. Neon will provide your connection string, formatted like:
   ```text
   postgresql://<username>:<password>@ep-<project-id>.ap-southeast-1.aws.neon.tech/neondb?sslmode=require
   ```
5. Copy this URL. RecallOS automatically normalizes `postgres://` or `postgresql://` and tunes the connection pool (`pool_size=3`, `max_overflow=2`, `pool_pre_ping=True`) for Neon free tier limits.

---

## 3. Step 2: Deploy to Render

### Option A: Using `render.yaml` Blueprint (Recommended)
1. Push your repository to GitHub.
2. In the [Render Dashboard](https://dashboard.render.com/), click **New > Blueprint**.
3. Select your repository. Render will detect `render.yaml` and configure the web service:
   - **Service Name:** `recallos-backend`
   - **Root Directory:** `backend`
   - **Plan:** `free`
   - **Region:** `singapore`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT --no-access-log --proxy-headers --forwarded-allow-ips="*"`
   - **Health Check Path:** `/health`
4. Enter the required environment variable values when prompted.

### Option B: Manual Web Service Setup
If creating a Web Service manually:
- **Language / Environment:** Python
- **Root Directory:** `backend`
- **Region:** `Singapore`
- **Plan:** `Free`
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:**
  ```bash
  alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT --no-access-log --proxy-headers --forwarded-allow-ips="*"
  ```
- **Health Check Path:** `/health`

---

## 4. Step 3: Configure Environment Variables

Set the following environment variables in the Render Service settings:

| Variable Name | Required | Example / Description |
|---|---|---|
| `PYTHON_VERSION` | Yes | `3.13.7` |
| `ENV` | Yes | `production` |
| `DATABASE_URL` | Yes | `postgresql://user:password@ep-xyz.ap-southeast-1.aws.neon.tech/neondb?sslmode=require` |
| `JWT_SECRET` | Yes | 32+ character random secret (e.g. `openssl rand -hex 32`) |
| `JWT_EXPIRE_MINUTES` | Yes | `1440` (24 hours) |
| `GEMINI_API_KEY` | Yes | Your Google Gemini API Key |
| `GEMINI_MODEL` | Yes | `gemini-1.5-flash` |
| `ALLOWED_ORIGINS` | Yes | Comma-separated frontend URLs (e.g. `https://recallos.onrender.com`). No trailing slashes. No `*` wildcards allowed in production. |
| `MAX_UPLOAD_MB` | Yes | `10` |
| `DAILY_CARD_LIMIT` | Yes | `50` |
| `ENABLE_DUEL` | Yes | `true` |

---

## 5. Step 4: Verify Deployment

Once Render finishes building and starting the service:

1. **Uptime Health Check:**
   ```bash
   curl -i https://<your-render-url>.onrender.com/health
   ```
   **Expected Response (HTTP 200):**
   ```json
   {"status": "ok"}
   ```

2. **Database Connectivity Health Check:**
   ```bash
   curl -i https://<your-render-url>.onrender.com/health/db
   ```
   **Expected Response (HTTP 200):**
   ```json
   {"status": "ok", "db": "connected"}
   ```

---

## 6. Step 5: Run Seed Data Locally Against Neon

To populate initial cards, deck, and historical reviews into the remote Neon database:

1. Open a local terminal in the `backend` folder.
2. Temporarily set your Neon database URL and `ENV=development` (the seed script refuses to run if `ENV=production`):
   ```powershell
   # PowerShell
   $env:DATABASE_URL="postgresql://user:password@ep-xyz.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"
   $env:ENV="development"
   python scripts/seed.py
   ```
   ```bash
   # Bash / Linux / macOS
   DATABASE_URL="postgresql://user:password@ep-xyz.ap-southeast-1.aws.neon.tech/neondb?sslmode=require" ENV=development python scripts/seed.py
   ```
3. The script will apply migrations, create `testuser@example.com` (password: `password123`), 30 cards, and 80 historical reviews.

---

## 7. Important Operational Notes

### Free Tier Sleep & Uptime Monitoring
- **Render Free Tier Spin-Down:** Render web services sleep after ~15 minutes of inactivity. The first request after sleeping takes **30 to 60 seconds** to wake up (cold start).
- **Keep-Alive Ping:** Configure an external uptime monitor (e.g. [UptimeRobot](https://uptimerobot.com/)) to send an HTTP GET request every 5 minutes to:
  ```text
  https://<your-render-url>.onrender.com/health
  ```
- **CRITICAL:** **Ping ONLY `/health`, NEVER `/health/db`**. Pinging `/health/db` triggers database queries on every ping, which prevents the Neon free tier database from sleeping when idle and exhausts Neon compute hours.

### Single-Worker Architecture Invariant
- The start command runs uvicorn with exactly **one worker** (no `--workers` flag).
- **Rationale:** The in-memory IP rate limiter (`InMemoryRateLimiter`), WebSocket room manager (`ConnectionManager`), and Quiz Duel session state are held in-memory. Running multiple worker processes would partition this state and break WebSocket synchronization.
