# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Layout

- `backend/` — FastAPI API (Python). Runs on port 9090.
- `frontend/` — Next.js chat UI (`frontend/app/page.tsx`). Talks to the backend at `NEXT_PUBLIC_API_BASE_URL` (default `http://localhost:9090`).
- `documents/`, `sources.json`, `chroma_db/`, `data/` live at the repo root and are shared with the backend (bind-mounted in Docker, `../` paths when run locally from `backend/`).

## Commands

```bash
# Backend, run locally (from backend/)
./dev.sh install   # create backend/.venv and install dependencies
./dev.sh ingest    # embed documents into ChromaDB (re-run when documents change)
./dev.sh start     # start API with --reload
./dev.sh serve     # start API without --reload

# Frontend (from frontend/)
npm install
npm run dev        # http://localhost:3000

# Docker (from repo root)
./dev.sh up        # backend container at http://localhost:9090
./dev.sh prod-up   # nginx + backend + certbot
```

There are no automated tests. Manual testing is done via the chat UI, the `/debug/search?q=...` endpoint (bypasses the LLM, shows raw retrieval results), or the `/eval` page.

## Architecture

Three-agent RAG pipeline, all wired together in `backend/app/orchestrator.py`:

1. **Retriever** (`backend/app/retriever.py`) — embeds the user query with `all-MiniLM-L6-v2` (local, via sentence-transformers), fetches top-K passages from ChromaDB. Returns dicts with `text`, `source`, `citation`, `url`, `page`, `distance`.

2. **Generator** (`backend/app/generator.py`) — sends retrieved passages + conversation history to an OpenRouter LLM. The system prompt is `GENERATOR_SYSTEM` in `backend/app/prompts.py`.

3. **Grounder** (`backend/app/critic.py`) — a second LLM call that reviews the draft answer against the same passages, adds citations, and corrects doctrinal errors. Returns JSON `{verdict, note, revised_answer}`.

All LLM calls go through `backend/app/client.py:_call_agent`, which uses the OpenAI SDK pointed at OpenRouter's base URL.

## Admin pages

Behind HTTP Basic auth (`require_admin` in `backend/app/main.py`), and disabled entirely while `ADMIN_PASSWORD` is unset:

- `/eval` — side-by-side comparison of one question across configs (model, top_k). `POST /eval` is the JSON API; the pipeline for one config is `backend/app/eval_runner.py`.
- `/messages` — submissions from the frontend's "Suggestions & feedback" form (`POST /contact`, public), stored one JSON object per line in `MESSAGES_FILE`.
- `/docs`, `/openapi.json` — FastAPI's API docs.

## Key configuration

`backend/app/config.py` reads from `.env` (see `backend/.env.example`). Important vars for development:

| Var | What it controls |
|-----|-----------------|
| `OPENROUTER_API_KEY` | Required |
| `OPENROUTER_AGENT` | Generator model (default: `google/gemini-2.5-flash-preview`) |
| `OPENROUTER_REVIEWER_AGENT` | Grounder model |
| `TOP_K_CHUNKS` | Number of passages retrieved per query (default: 5) |
| `ADMIN_USER` / `ADMIN_PASSWORD` | Login for the admin pages |
| `MESSAGES_FILE` | Where feedback is stored (default `../data/messages.jsonl`; `/app/data/messages.jsonl` in Docker) |
| `CORS_EXTRA_ORIGINS` | Frontend origins allowed to call the API |
| `LOG_LEVEL` | Set to `DEBUG` to see retrieval + LLM details |

## Prompts

Prompts live in `backend/app/prompts.py`:

- `GENERATOR_SYSTEM` — senior teacher style: thorough, authoritative, cites passages inline. Uses `{context}` and `{history}` template variables filled by `generator.py`.
- `GROUNDER_SYSTEM` — used by the grounder in `backend/app/critic.py`.

## Ingestion

`backend/app/ingest.py` reads PDFs/TXTs from `documents/`, chunks them, embeds with sentence-transformers, and stores in ChromaDB. Source metadata (title, author, chapter map, URL) lives in `sources.json` — ingest resolves which chapter each chunk belongs to and builds a `citation` string (e.g. `"The Art of Living, Ch. 4 — The Root of the Problem, p. 58"`). Re-ingesting rebuilds the collection from scratch to keep citations consistent.

## UI

The chat UI is `frontend/app/page.tsx` (React, `react-markdown` + `rehype-sanitize`), styled by `frontend/app/globals.css`. Sources appear as a collapsible panel below each AI message; the feedback tab and form are in `frontend/app/FeedbackTab.tsx`. The admin pages are self-contained HTML strings in `backend/app/main.py` (`_EVAL_HTML`, `_MESSAGES_HTML`).
