# RecallOS: PRD and Antigravity Build Prompts

*End-Term Software Project. Deadline: 27 Oct 2026, 11:59 PM IST.*

## 0. How to use this document in Antigravity

1. Create an empty repo folder, open it in Antigravity, and save this file as `PRD.md` in the repo root.
2. Give the agent the **Master Prompt** (Section 1) first.
3. Then feed the **Phase Prompts** (Section 11) one at a time. Review the diff and commit after each phase before moving on.
4. Do not paste the whole PRD plus all phases in one go. Agents drift when the task is too large.

## 1. Master Prompt (paste this first)

```text
You are a senior full-stack engineer. Read PRD.md in the repo root fully before writing any code.
We are building RecallOS exactly as described there. Rules you must follow for the whole project:

1. Follow the stack, folder structure, data model, API and WebSocket protocol in PRD.md. Do not swap technologies.
2. Work phase by phase. Only do the phase I ask for. Do not build features from later phases.
3. After finishing each phase, run the tests/linters, fix failures, then make a git commit with a meaningful message (conventional style, e.g. "feat(auth): add JWT login and register"). Make small, frequent commits. Never one giant commit.
4. Never hardcode secrets. All keys live in .env (git-ignored). Maintain .env.example with every variable and no real values.
5. Every endpoint validates input with Pydantic, returns consistent JSON errors {"error": {"code": str, "message": str}}, and uses correct HTTP status codes.
6. Every UI screen must have loading, empty, success and error states.
7. Write the SM-2 logic as pure functions with unit tests. Do not use an SM-2 library.
8. Keep code readable: type hints, short functions, docstrings on non-obvious logic.
9. If something in PRD.md is ambiguous, pick the simplest option, note it in docs/DECISIONS.md, and continue.

Confirm you have read PRD.md by summarising the product in 5 lines, then wait for the Phase 1 prompt.
```

## 2. Product Overview

**Name:** RecallOS

**One line:** Upload your notes, get flashcards automatically, and revise them on a scientifically scheduled plan that adapts to your exam date.

**Problem statement:** Students re-read notes before exams and forget most of it within days. Making flashcards by hand takes hours, and deciding what to revise on which day is guesswork. Students end up cramming, with no idea which topics are actually weak.

**Target users:** College and bootcamp students preparing for exams or certifications, who have notes in PDF or text form and 2 to 8 weeks before the exam.

**Solution:** RecallOS converts notes into flashcards using an LLM, schedules every card with the SM-2 spaced repetition algorithm, prioritises cards using the exam date and weak topics, shows analytics on retention, and lets two friends compete in a live quiz on the same deck.

**Why it needs to be software:** The scheduling state of hundreds of cards per user changes after every review. Doing this by hand is not realistic, and the live duel needs real-time server logic.

## 3. Scope

### In scope (the 5 workflows)

1. **Auth:** register, login, private user data.
2. **Upload to cards with live progress (WebSocket):** upload PDF or TXT, chunk it, generate cards with an LLM in a background job, stream progress live.
3. **Daily review (SM-2):** due cards, rating buttons, schedule update.
4. **Dashboard and exam mode:** topic accuracy, streak, 30-day forecast, weak topics, expected retention on exam day, exam-aware prioritisation.
5. **Quiz Duel (WebSocket):** two players, room code, 10 multiple-choice rounds, server-authoritative scoring.

### Out of scope (do NOT build)

Social login, payments, mobile app, OCR for scanned PDFs, image cards, 3+ player duels, spectators, chat, matchmaking, reconnect and resume in duels, email notifications.

## 4. Tech Stack

| Layer | Choice | Reason |
| --- | --- | --- |
| Backend | Python 3.11, FastAPI, Uvicorn | Native WebSocket support, fast to build |
| ORM and migrations | SQLAlchemy 2.x, Alembic | Standard, clean schema history |
| Database | PostgreSQL (Neon free tier) | Relational data, free hosting |
| Auth | JWT (access token) with bcrypt password hashing | Simple and secure enough |
| PDF parsing | pypdf | Light, no system dependencies |
| LLM | Google Gemini API (free tier), behind a `LLMClient` interface | Easy to swap provider |
| Background jobs | FastAPI `BackgroundTasks` plus a DB-backed `jobs` table | No Celery needed in 2 days |
| Frontend | React 18 + Vite + TypeScript + Tailwind CSS | Quick to build |
| Charts | Recharts | Supports axis labels and legends |
| Tests | pytest (backend) | SM-2 and duel logic tests |
| Deploy | Backend on Render (WebSockets allowed), frontend on Vercel, DB on Neon | Free tiers |

The frontend on Vercel must call the Render backend over HTTPS and WSS using `VITE_API_URL` and `VITE_WS_URL`. CORS must allow only the Vercel domain and localhost.

## 5. Architecture

```text
Browser (React)
   |  REST (JSON, JWT in Authorization header)
   |  WebSocket (JWT as ?token= query param)
   v
FastAPI app
   |-- routers/        auth, decks, uploads, cards, reviews, stats, duels
   |-- services/       sm2.py, generator.py, scheduler.py, stats.py, duel_engine.py
   |-- ws/             connection_manager.py, generate_ws.py, duel_ws.py
   |-- llm/            base.py (LLMClient), gemini.py
   |-- models/         SQLAlchemy models
   |-- core/           config.py, security.py, errors.py, db.py
   v
PostgreSQL
```

**ConnectionManager (shared by both WebSocket features):** keeps a dict of `room_id -> set[WebSocket]`, with `connect`, `disconnect`, `send_to`, and `broadcast(room_id, message)`. Generation uses room `job:{job_id}`. Duels use room `duel:{room_code}`. Dead sockets are removed on send failure.

**Important design rule:** job status is always saved in the DB. The WebSocket is only a live view of it. If the socket drops, the frontend falls back to polling `GET /api/jobs/{id}` so nothing is lost.

## 6. Data Model

| Table | Key columns |
| --- | --- |
| `users` | id, email (unique), password\_hash, display\_name, exam\_date (nullable), created\_at |
| `decks` | id, user\_id, title, source\_filename, file\_hash, created\_at. Unique on (user\_id, file\_hash) to block duplicate uploads |
| `jobs` | id, user\_id, deck\_id, status (`queued`, `processing`, `ready`, `failed`), total\_chunks, done\_chunks, cards\_created, error\_message, created\_at, finished\_at |
| `cards` | id, deck\_id, topic, question, answer, distractors (JSON list of 3 wrong answers), created\_at |
| `card_states` | card\_id, user\_id, ease\_factor (default 2.5), interval\_days, repetitions, due\_date, last\_reviewed\_at, lapses |
| `reviews` | id, user\_id, card\_id, rating (1, 2, 3, 4), reviewed\_at, prev\_interval, new\_interval |
| `duels` | id, room\_code, deck\_id, host\_id, guest\_id (nullable), status (`waiting`, `active`, `finished`, `abandoned`), host\_score, guest\_score, winner\_id (nullable), created\_at, finished\_at |

Add indexes on `card_states(user_id, due_date)` and `reviews(user_id, reviewed_at)`.

## 7. Core Logic Specifications

### 7.1 SM-2 scheduling (pure function, unit tested)

Ratings map to quality values: Again = 1, Hard = 3, Good = 4, Easy = 5.

```text
Input: ease_factor (EF), interval, repetitions, quality q

if q < 3:
    repetitions = 0
    interval = 1
    lapses += 1
else:
    if repetitions == 0: interval = 1
    elif repetitions == 1: interval = 6
    else: interval = round(interval * EF)
    repetitions += 1

EF = EF + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
EF = max(EF, 1.3)
due_date = today + interval days
```

Required unit tests: first review with Good gives interval 1, second gives 6, third uses EF; Again resets repetitions and interval; EF never drops below 1.3; Easy raises EF; Hard lowers EF.

### 7.2 Exam mode

If the user has set `exam_date`:

1. After SM-2 computes `due_date`, cap it so that it is never later than `exam_date - 1 day` (but never earlier than tomorrow).
2. Today's review queue is sorted by priority score: `priority = (1 - topic_accuracy) * 0.6 + overdue_days_normalised * 0.4`. Weak topics and overdue cards come first.
3. The queue returns at most a configurable daily limit (default 50 cards) and the dashboard shows how many are left over.

Without an exam date, the queue is simply sorted by due date.

### 7.3 Analytics

- **Topic accuracy:** share of reviews with rating 3 or 4 (Good or Easy) per topic over the last 30 days.
- **Weak topics:** topics with accuracy below 60% and at least 5 reviews, sorted ascending.
- **Streak:** consecutive days (ending today or yesterday) with at least one review.
- **30-day forecast:** for each of the next 30 days, count of cards whose `due_date` falls on that day, with overdue cards counted on day 0.
- **Expected retention on exam day:** for each card, estimate recall probability as `exp(-t / S)` where `t` = days between last review and exam date, and `S` = current `interval_days` (minimum 1). Report the average across all cards as a percentage. Label it clearly as an estimate on the dashboard. This is an approximation of the forgetting curve, not a claim of exact prediction.

### 7.4 Card generation pipeline

1. Validate file: type must be PDF or TXT, max 10 MB. Reject otherwise with a clear message.
2. Compute SHA-256 of file. If this user already uploaded the same hash, return 409 with the existing deck id.
3. Extract text. If a PDF yields almost no text (under 200 characters), mark as failed with the message "This looks like a scanned PDF. Please upload a text-based PDF."
4. Split text into chunks of roughly 1,500 characters on paragraph boundaries, with small overlap.
5. Create a `jobs` row (`queued`), return the job id immediately, and start the background task.
6. For each chunk, call the LLM with a strict JSON prompt: return up to 5 cards, each with `topic`, `question`, `answer`, and exactly 3 plausible but wrong `distractors`. Parse and validate the JSON. Retry up to 2 times with exponential backoff on API error, timeout, or invalid JSON. If a chunk still fails, skip it, record it, and continue.
7. Drop duplicate questions (case-insensitive match). Insert cards and initial `card_states` (due today).
8. After each chunk, update `jobs.done_chunks` and broadcast a `chunk_done` event.
9. At the end, set status `ready` if at least 1 card was created, otherwise `failed` with a message.

## 8. API Specification

All endpoints are under `/api`. All except register and login require `Authorization: Bearer <token>`.

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/auth/register` | Create user. Body: email, password (min 8 chars), display\_name |
| POST | `/auth/login` | Returns access token |
| GET | `/me` | Current user |
| PATCH | `/me` | Update display\_name and exam\_date |
| POST | `/uploads` | Multipart file plus optional title. Returns `{deck_id, job_id}` |
| GET | `/jobs/{id}` | Job status (polling fallback) |
| GET | `/decks` | List own decks with card counts |
| GET | `/decks/{id}/cards` | List cards of a deck |
| DELETE | `/decks/{id}` | Delete deck, its cards and states |
| GET | `/reviews/queue` | Today's due cards (exam-aware ordering) |
| POST | `/reviews` | Body: card\_id, rating (1 to 4). Applies SM-2, stores review, returns new state |
| GET | `/stats/overview` | Streak, due today, total cards, reviews last 7 days, expected retention |
| GET | `/stats/topics` | Topic accuracy list |
| GET | `/stats/forecast` | 30-day due forecast |
| POST | `/duels` | Create duel room for a deck (needs at least 10 cards). Returns room\_code |
| GET | `/duels/{room_code}` | Room info |
| GET | `/duels/history` | Past duels of the user |

Authorization rule: a user can only read or modify their own decks, cards, states and jobs. Return 404 (not 403) for other people's resources.

## 9. WebSocket Protocol

All messages are JSON of the form `{"type": "...", "data": {...}}`. The server verifies the JWT from `?token=` on connect and closes with code 4401 if invalid.

### 9.1 Live generation: `/ws/generate/{job_id}`

Only the job owner may connect. On connect the server immediately sends the current job snapshot, so late joiners are in sync.

| Direction | type | data |
| --- | --- | --- |
| Server to client | `snapshot` | status, done\_chunks, total\_chunks, cards\_created |
| Server to client | `chunk_done` | chunk\_index, total\_chunks, new\_cards (list of cards just created), cards\_created |
| Server to client | `chunk_failed` | chunk\_index, reason |
| Server to client | `ready` | deck\_id, cards\_created |
| Server to client | `failed` | message |

Frontend shows a progress bar ("Chunk 3 of 12"), a live-growing list of cards, and a clear error state with a retry button on `failed`.

### 9.2 Quiz Duel: `/ws/duel/{room_code}`

Server is the single source of truth. The client never sends scores or correctness.

Room rules: host connects first, guest joins with the code. The duel starts automatically when both are connected. Server picks 10 random cards of the deck, and for each builds 4 options (1 answer plus 3 distractors, shuffled by the server).

| Direction | type | data |
| --- | --- | --- |
| Server to client | `room_state` | status, players (names), you |
| Server to client | `player_joined` | display\_name |
| Server to client | `countdown` | seconds (3 to 1 before start) |
| Server to client | `question` | index, total, question, options (list of 4 strings), deadline\_ms (15000) |
| Client to server | `answer` | question\_index, option\_index |
| Server to client | `answer_result` | question\_index, first\_correct\_player (id or null), correct\_option\_index, scores |
| Server to client | `round_end` | winner\_id (or null for tie), final\_scores |
| Server to client | `opponent_left` | message |
| Server to client | `error` | code, message |

Scoring and rules:

- Each question has a 15 second timer owned by the server (asyncio task).
- The first player to submit the correct option gets 10 points and the question ends immediately for both players.
- A wrong answer locks that player out for that question. If both are wrong, or the timer runs out, no one scores.
- Ignore duplicate or late answers (wrong question\_index, already answered, after deadline). Use a per-room `asyncio.Lock` so two simultaneous answers are processed one at a time.
- If a player disconnects mid-duel: cancel timers, send `opponent_left` to the other player, mark the duel `abandoned`, and declare the remaining player the winner in the result. No reconnect support.
- Rooms in memory are cleaned up when the duel ends or all sockets are gone. Duel result is saved to the `duels` table.

## 10. Frontend Screens

1. **Auth:** login and register with inline validation errors.
2. **Home or Dashboard:** due-today count with a Start Review button, streak, expected retention on exam day, topic accuracy bar chart, 30-day forecast line chart, weak topics list. All charts need a title, axis labels, and legend where there is more than one series.
3. **Upload:** drag-and-drop file box, title field, then the live generation view (progress bar plus streaming cards).
4. **Decks:** list with card counts, delete, and a Start Duel button.
5. **Review:** one card at a time, Show Answer, then Again, Hard, Good, Easy buttons with the next interval shown on each button. Empty state when nothing is due.
6. **Duel:** create or join by code, waiting room, live question screen with a 15 second timer bar, live scoreboard, final result screen.
7. **Settings:** display name and exam date.

Global: toast for success and errors, skeleton or spinner for loading, and a friendly empty state on every list.

## 11. Error Handling Checklist

- Wrong file type, oversize file, empty file, corrupt PDF, scanned PDF: clear messages.
- Duplicate upload: tell the user and link to the existing deck.
- LLM down, rate-limited, timeout, or returns invalid JSON: retry with backoff, then skip the chunk and continue; show it in the UI.
- JWT expired: frontend redirects to login with a message.
- Review submitted for a card that is not the user's: 404.
- Duel: room not found, room full, deck has fewer than 10 cards, joining your own room, answer after deadline.
- WebSocket drop on generation: frontend reconnects and falls back to polling.
- Global exception handler returns the standard error JSON and never leaks stack traces.

## 12. Security Checklist

- Passwords hashed with bcrypt, never logged.
- All secrets in `.env`, which is in `.gitignore`. Provide `.env.example`.
- Required env vars: `DATABASE_URL`, `JWT_SECRET`, `JWT_EXPIRE_MINUTES`, `GEMINI_API_KEY`, `ALLOWED_ORIGINS`, `MAX_UPLOAD_MB`, `DAILY_CARD_LIMIT`.
- Pydantic validation on every request body. File size and type validated server-side.
- Per-user ownership checks on every resource.
- Basic rate limit on login and upload endpoints.
- Never trust client data in duels.

## 13. Repository Structure

```text
recallos/
  PRD.md
  README.md
  docs/DECISIONS.md
  .env.example
  .gitignore
  backend/
    app/ (main.py, core/, models/, routers/, services/, ws/, llm/)
    alembic/
    tests/ (test_sm2.py, test_exam_mode.py, test_duel_engine.py, test_auth.py, test_upload.py)
    requirements.txt
  frontend/
    src/ (pages/, components/, api/, hooks/, lib/)
    package.json
```

## 14. Phase Prompts (feed one at a time)

### Phase 1: Skeleton, DB and Auth

```text
Phase 1 only. Set up the repo structure from PRD.md Section 13, backend FastAPI app with config via env, SQLAlchemy models for ALL tables in Section 6, Alembic initial migration, and the auth endpoints (register, login, GET/PATCH /me) with bcrypt and JWT. Add the standard error format and global exception handler. Add .gitignore and .env.example. Write pytest tests for register, login, wrong password, duplicate email. Commit in small steps. Stop after this phase.
```

### Phase 2: SM-2 and Review API

```text
Phase 2 only. Implement services/sm2.py exactly as in PRD Section 7.1 as pure functions, with full unit tests listed there. Implement exam-mode capping and priority sorting from Section 7.2. Implement GET /reviews/queue and POST /reviews with ownership checks. Seed script that inserts a sample deck of 30 cards for a test user so I can try it. Commit after each logical piece. Stop after this phase.
```

### Phase 3: Upload and Generation Pipeline

```text
Phase 3 only. Implement the pipeline in PRD Section 7.4: POST /uploads, file validation, SHA-256 duplicate detection, pypdf extraction, chunking, LLMClient interface plus Gemini implementation, background job with retries and per-chunk failure handling, jobs table updates, and GET /jobs/{id}. No WebSocket yet. Mock the LLM in tests and test: duplicate upload, scanned PDF, invalid JSON from LLM, partial chunk failure. Stop after this phase.
```

### Phase 4: ConnectionManager and Live Generation WebSocket

```text
Phase 4 only. Implement ws/connection_manager.py and the /ws/generate/{job_id} endpoint exactly per PRD Section 9.1, including JWT auth on connect, owner-only access, initial snapshot, and broadcasting events from the background job. Make sure the job still completes if no socket is connected. Add a test that connects a socket and receives chunk_done and ready events. Stop after this phase.
```

### Phase 5: Stats and Analytics API

```text
Phase 5 only. Implement /stats/overview, /stats/topics, /stats/forecast following PRD Section 7.3 exactly (streak, topic accuracy, weak topics, 30-day forecast, expected retention on exam day). Add unit tests with hand-computed expected values. Stop after this phase.
```

### Phase 6: Frontend (core)

```text
Phase 6 only. Build the React + Vite + TypeScript + Tailwind frontend for screens 1 to 5 and 7 in PRD Section 10: auth, dashboard with Recharts charts (titles, axis labels, legends), upload with the live generation view over WebSocket (with polling fallback), decks, review, settings. Every screen needs loading, empty, success and error states. Use VITE_API_URL and VITE_WS_URL. Stop after this phase.
```

### Phase 7: Quiz Duel (backend and frontend)

```text
Phase 7 only. Implement duel_engine.py (pure game logic, no socket code), the /ws/duel/{room_code} endpoint, POST /duels, GET /duels/{room_code}, GET /duels/history exactly per PRD Section 9.2. Use a per-room asyncio.Lock, server-owned timers, and the disconnect rule. Write unit tests for the engine: first-correct wins, wrong answer lockout, timeout, duplicate/late answers, disconnect. Then build the Duel screen (create or join by code, waiting room, question screen with timer bar, scoreboard, result). Put the whole feature behind an env flag ENABLE_DUEL so it can be switched off. Stop after this phase.
```

### Phase 8: Deploy, Polish and Docs

```text
Phase 8 only. Prepare deployment: Dockerfile or Render start command for backend, render.yaml if useful, Vercel config for frontend, CORS from ALLOWED_ORIGINS, health check endpoint. Write the README with all sections required by the project guidelines (Project Name, Problem Statement, Target Users, Solution, Key Features, Tech Stack, Architecture with a diagram, Local Setup, Environment Variables, Deployment links). Add docs/DECISIONS.md. Run a final check that no secrets are in the repo or git history. Stop after this phase.
```

## 15. Acceptance Criteria (definition of done)

- [ ] A new user can register, upload a text-based PDF, and watch cards appear live.
- [ ] Uploading the same file twice is blocked with a clear message.
- [ ] A scanned PDF and a corrupt file each give a readable error.
- [ ] Review ratings change the next due date as per SM-2, verified by tests.
- [ ] Setting an exam date changes queue order and caps intervals.
- [ ] Dashboard shows topic accuracy, streak, 30-day forecast, weak topics and expected retention, all labelled.
- [ ] Two browsers can complete a 10-question duel, and closing one tab mid-duel ends it gracefully.
- [ ] User A cannot access user B's decks, jobs or cards.
- [ ] Deployed backend and frontend work over HTTPS and WSS.
- [ ] No secrets in repo, meaningful commit history, README complete.

## 16. Cut Rules (if time runs out)

1. First to cut: Quiz Duel. Set `ENABLE_DUEL=false`, hide the menu item, and do not mention it in the README or demo.
2. Second: the expected-retention metric (keep the forecast and topic accuracy).
3. Never cut: auth, upload to cards, SM-2 review, tests, deployment, README.

## 17. Demo Video Script (3 to 5 minutes)

1. **0:00 to 0:30:** The problem (cramming, forgetting) and who RecallOS is for.
2. **0:30 to 1:30:** Upload a PDF, show cards streaming in live.
3. **1:30 to 2:30:** Review session, rating buttons, show how intervals change, set an exam date and show the queue reorder.
4. **2:30 to 3:15:** Dashboard walkthrough.
5. **3:15 to 4:30:** Quiz Duel between two browser windows.
6. **4:30 to 5:00:** One architecture slide (ConnectionManager, server-authoritative duel, SM-2 as pure tested logic) and the GitHub link.
