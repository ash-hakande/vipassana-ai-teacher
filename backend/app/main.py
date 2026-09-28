import logging

import asyncio
import html
import json
import os
import secrets
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.config import Config, config
from app.eval_runner import run_eval_config
from app.models import (
    ContactRequest,
    EndSessionResponse,
    EvalRequest,
    EvalResponse,
    HealthResponse,
    RespondRequest,
    RespondResponse,
    StartSessionResponse,
    create_session,
    get_session,
)
from app.orchestrator import Orchestrator

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Vipassana AI Assistant",
    description="Multi-agent RAG chatbot grounded in Vipassana teaching documents",
    version="0.1.0",
    # Served below behind the admin login instead
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=Config.cors_origins(),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

_orchestrator: Orchestrator = None
_basic_auth = HTTPBasic()


def require_admin(creds: HTTPBasicCredentials = Depends(_basic_auth)):
    if not config.ADMIN_PASSWORD:
        raise HTTPException(status_code=503, detail="Admin pages are disabled: set ADMIN_PASSWORD in .env")
    user_ok = secrets.compare_digest(creds.username.encode(), config.ADMIN_USER.encode())
    pass_ok = secrets.compare_digest(creds.password.encode(), config.ADMIN_PASSWORD.encode())
    if not (user_ok and pass_ok):
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )


@app.on_event("startup")
async def startup():
    global _orchestrator
    Config.validate()
    _orchestrator = Orchestrator()
    logger.info("Vipassana AI Assistant started on port %s", config.PORT)


@app.get("/openapi.json", include_in_schema=False, dependencies=[Depends(require_admin)])
async def openapi_schema():
    return app.openapi()


@app.get("/docs", include_in_schema=False, dependencies=[Depends(require_admin)])
async def api_docs():
    return get_swagger_ui_html(openapi_url="/openapi.json", title=f"{app.title} — API docs")


# ── Endpoints ──────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
async def health():
    try:
        count = _orchestrator.retriever._collection.count()
    except Exception:
        count = 0
    return {"status": "ok", "documents_indexed": count}


@app.get("/debug/search")
async def debug_search(q: str = Query(..., description="Search query")):
    """Show raw retrieval results for a query — bypasses generator and critic."""
    chunks = await asyncio.to_thread(_orchestrator.retriever.retrieve, q)
    return {
        "query": q,
        "chunks_found": len(chunks),
        "chunks": [
            {
                "chunk_id": c["chunk_id"],
                "source": c["source"],
                "distance": round(c["distance"], 4),
                "text": c["text"],
            }
            for c in chunks
        ],
    }


@app.post("/session/start", response_model=StartSessionResponse)
async def start_session():
    session = create_session()
    return {
        "session_id": session.id,
        "message": (
            "Welcome. I am here to help you explore the teachings of Vipassana "
            "as described in the provided texts. What would you like to understand?"
        ),
        "status": "active",
    }


@app.post("/session/{session_id}/respond", response_model=RespondResponse)
async def respond(session_id: str, body: RespondRequest):
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status != "active":
        raise HTTPException(status_code=400, detail="Session is not active")
    try:
        result = await _orchestrator.respond(session_id, body.message)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("[respond] error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/session/{session_id}/end", response_model=EndSessionResponse)
async def end_session(session_id: str):
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    session.status = "ended"
    turn_count = sum(1 for t in session.history if t.role == "user")
    return {"session_id": session_id, "status": "ended", "turn_count": turn_count}


@app.post("/eval", response_model=EvalResponse, dependencies=[Depends(require_admin)])
async def run_eval(body: EvalRequest):
    """Run one question through several configs in parallel for side-by-side comparison."""
    if not body.configs:
        raise HTTPException(status_code=400, detail="At least one config is required")
    results = await asyncio.gather(*(
        run_eval_config(body.question, cfg, _orchestrator.retriever, _orchestrator.grounder)
        for cfg in body.configs
    ))
    return {"question": body.question, "results": results}


@app.get("/eval", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
async def eval_ui():
    models = list(dict.fromkeys([
        config.OPENROUTER_GENERATOR_AGENT,
        config.OPENROUTER_REVIEWER_AGENT,
        "google/gemini-2.5-flash",
        "google/gemini-2.5-pro",
    ]))
    return _EVAL_HTML.replace("__MODELS__", json.dumps(models))


# ── Reach-out messages ─────────────────────────────────────────────────────

_messages_lock = asyncio.Lock()


def _append_message(entry: dict):
    os.makedirs(os.path.dirname(config.MESSAGES_FILE) or ".", exist_ok=True)
    with open(config.MESSAGES_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _read_messages() -> list:
    try:
        with open(config.MESSAGES_FILE, encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return []
    messages = []
    for line in lines:
        try:
            messages.append(json.loads(line))
        except json.JSONDecodeError:
            logger.warning("[messages] skipping malformed line")
    return messages


@app.post("/contact", status_code=201)
async def contact(body: ContactRequest):
    message = body.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message is empty")
    if body.website:
        return {"status": "received"}
    entry = {
        "received_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "name": body.name.strip(),
        "email": body.email.strip(),
        "message": message,
    }
    async with _messages_lock:
        await asyncio.to_thread(_append_message, entry)
    logger.info("[contact] message received (%d chars)", len(message))
    return {"status": "received"}


@app.get("/messages", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
async def messages_ui():
    messages = await asyncio.to_thread(_read_messages)
    rows = []
    for msg in reversed(messages):
        email = html.escape(msg.get("email", ""))
        sender = html.escape(msg.get("name", "")) or "Anonymous"
        if email:
            sender += f' &lt;<a href="mailto:{email}">{email}</a>&gt;'
        rows.append(
            f'<article><div class="meta"><span>{sender}</span>'
            f'<time>{html.escape(msg.get("received_at", ""))}</time></div>'
            f'<p>{html.escape(msg.get("message", ""))}</p></article>'
        )
    body = "".join(rows) or '<p class="empty">No messages yet.</p>'
    return _MESSAGES_HTML.replace("__COUNT__", str(len(messages))).replace("__ROWS__", body)


_EVAL_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Eval Comparison</title>
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/dompurify@3/dist/purify.min.js"></script>
  <style>
    * { box-sizing: border-box; }
    body {
      font-family: Georgia, 'Times New Roman', serif;
      background: #f5f0e8;
      color: #2c2417;
      margin: 0;
      padding: 20px 16px 40px;
    }
    h1 { font-size: 1.3rem; font-weight: normal; margin: 0 0 14px; color: #5a3c10; }
    h1 a { font-size: 0.8rem; color: #7a5c2a; margin-left: 10px; }
    .ask { display: flex; gap: 10px; margin-bottom: 16px; }
    .ask textarea {
      flex: 1; min-height: 60px; padding: 10px; font: inherit; font-size: 0.95rem;
      border: 1px solid #c8b896; border-radius: 6px; background: #fffdf8; resize: vertical;
    }
    button {
      font: inherit; font-size: 0.9rem; cursor: pointer; border-radius: 6px;
      border: 1px solid #8b5e2a; background: #8b5e2a; color: #fff; padding: 8px 18px;
    }
    button.secondary { background: #f8f4ec; color: #7a5c2a; border-color: #c8b896; }
    button:disabled { opacity: 0.5; cursor: default; }
    .grid { display: grid; grid-template-columns: repeat(var(--cols, 2), minmax(0, 1fr)); gap: 14px; }
    @media (max-width: 800px) { .grid { grid-template-columns: 1fr; } .ask { flex-direction: column; } }
    .col {
      background: #fffdf8; border: 1px solid #d8ccb4; border-radius: 8px;
      padding: 12px; display: flex; flex-direction: column; gap: 10px; min-width: 0;
    }
    .controls { display: flex; flex-wrap: wrap; gap: 8px; align-items: end; }
    .controls label { display: flex; flex-direction: column; font-size: 0.72rem; color: #7a6a4a; gap: 3px; }
    .controls select, .controls input {
      font: inherit; font-size: 0.85rem; padding: 4px 6px;
      border: 1px solid #c8b896; border-radius: 4px; background: #faf8f3; max-width: 100%;
    }
    .controls .model { flex: 1; min-width: 160px; }
    .controls .model select, .controls .model input { width: 100%; }
    .remove { margin-left: auto; background: none; border: none; color: #b07040; padding: 2px 6px; font-size: 1.1rem; }
    .meta { font-size: 0.75rem; color: #7a6a4a; display: flex; flex-wrap: wrap; gap: 10px; }
    .badge { padding: 1px 7px; border-radius: 10px; background: #e6f0dc; color: #3f6a2a; }
    .badge.bad { background: #fdecea; color: #8b2b2b; }
    .note { font-size: 0.75rem; color: #b07040; font-style: italic; }
    .reply { font-size: 0.93rem; line-height: 1.6; overflow-wrap: anywhere; }
    .reply blockquote { margin: 8px 0; padding: 4px 12px; border-left: 3px solid #c8b896; color: #5a4a2a; }
    .reply p { margin: 0 0 10px; }
    .error { color: #8b2b2b; font-size: 0.85rem; white-space: pre-wrap; }
    .placeholder { color: #a89a7a; font-style: italic; font-size: 0.85rem; }
    details { font-size: 0.78rem; color: #5a4a2a; }
    summary { cursor: pointer; color: #7a5c2a; }
    .src { padding: 6px 0; border-bottom: 1px solid #ede5d5; }
    .src:last-child { border-bottom: none; }
    .src b { color: #5a3c10; }
    .src i { display: block; color: #7a6a4a; margin-top: 2px; }
  </style>
</head>
<body>
  <h1>Eval comparison <a href="/messages">messages &rarr;</a></h1>
  <div class="ask">
    <textarea id="question" placeholder="Ask a question to run through every config...">I feel strong pain in my knees while sitting</textarea>
    <div style="display:flex; flex-direction:column; gap:8px;">
      <button id="run">Run</button>
      <button id="add" class="secondary">+ Column</button>
    </div>
  </div>
  <div class="grid" id="grid"></div>

  <script>
    const MODELS = __MODELS__;
    const MAX_COLS = 4;
    const grid = document.getElementById('grid');

    function esc(s) {
      const d = document.createElement('div'); d.textContent = s ?? ''; return d.innerHTML;
    }

    function addColumn() {
      if (grid.children.length >= MAX_COLS) return;
      const col = document.createElement('div');
      col.className = 'col';
      const modelOpts = MODELS.map(m => `<option>${esc(m)}</option>`).join('') +
        '<option value="__other">Other...</option>';
      col.innerHTML = `
        <div class="controls">
          <label class="model">Model
            <select class="model-select">${modelOpts}</select>
            <input class="model-other" placeholder="provider/model-id" hidden>
          </label>
          <label>Top K
            <select class="topk"><option>3</option><option selected>5</option><option>8</option><option>10</option></select>
          </label>
          <button class="remove" title="Remove column">&times;</button>
        </div>
        <div class="out"><div class="placeholder">Results will appear here.</div></div>`;
      const sel = col.querySelector('.model-select');
      const other = col.querySelector('.model-other');
      sel.addEventListener('change', () => { other.hidden = sel.value !== '__other'; });
      col.querySelector('.remove').addEventListener('click', () => {
        if (grid.children.length > 1) { col.remove(); layout(); }
      });
      grid.appendChild(col);
      layout();
    }

    function layout() {
      grid.style.setProperty('--cols', grid.children.length);
      document.getElementById('add').disabled = grid.children.length >= MAX_COLS;
    }

    function readConfig(col) {
      const sel = col.querySelector('.model-select');
      const model = sel.value === '__other' ? col.querySelector('.model-other').value.trim() : sel.value;
      return {
        model: model,
        top_k: parseInt(col.querySelector('.topk').value, 10),
      };
    }

    function renderResult(out, r) {
      if (r.error) { out.innerHTML = `<div class="error">Error: ${esc(r.error)}</div>`; return; }
      const verdict = r.critic_approved
        ? '<span class="badge">approved</span>'
        : '<span class="badge bad">refused</span>';
      const sources = r.sources.map(s => {
        const label = esc(s.citation || s.source);
        const link = s.url ? `<a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">${label}</a>` : label;
        return `<div class="src"><b>${link}</b><i>${esc(s.text.trim().slice(0, 240))}...</i></div>`;
      }).join('');
      out.innerHTML = `
        <div class="meta">${verdict}<span>${(r.latency_ms / 1000).toFixed(1)}s</span><span>${r.reply.split(/ +/).length} words</span></div>
        ${r.critic_note ? `<div class="note">Grounder: ${esc(r.critic_note)}</div>` : ''}
        <div class="reply">${DOMPurify.sanitize(marked.parse(r.reply))}</div>
        <details><summary>Sources (${r.sources.length})</summary>${sources}</details>`;
    }

    async function run() {
      const question = document.getElementById('question').value.trim();
      if (!question) return;
      const cols = Array.from(grid.children);
      const configs = cols.map(readConfig);
      const badIdx = configs.findIndex(c => !c.model);
      if (badIdx >= 0) { alert('Column ' + (badIdx + 1) + ' needs a model id.'); return; }

      const btn = document.getElementById('run');
      btn.disabled = true; btn.textContent = 'Running...';
      cols.forEach(c => c.querySelector('.out').innerHTML = '<div class="placeholder">Running...</div>');
      try {
        const res = await fetch('/eval', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question, configs }),
        });
        if (!res.ok) throw new Error(res.status + ' ' + await res.text());
        const data = await res.json();
        data.results.forEach((r, i) => renderResult(cols[i].querySelector('.out'), r));
      } catch (e) {
        cols.forEach(c => c.querySelector('.out').innerHTML = `<div class="error">${esc(e.message)}</div>`);
      } finally {
        btn.disabled = false; btn.textContent = 'Run';
      }
    }

    document.getElementById('run').addEventListener('click', run);
    document.getElementById('add').addEventListener('click', addColumn);
    document.getElementById('question').addEventListener('keydown', e => {
      if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) run();
    });
    addColumn();
    addColumn();
  </script>
</body>
</html>
"""


_MESSAGES_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Reach-out Messages</title>
  <style>
    * { box-sizing: border-box; }
    body {
      font-family: Georgia, 'Times New Roman', serif;
      background: #f5f0e8;
      color: #2c2417;
      margin: 0;
      padding: 20px 16px 40px;
    }
    main { max-width: 760px; margin: 0 auto; }
    h1 { font-size: 1.3rem; font-weight: normal; margin: 0 0 14px; color: #5a3c10; }
    h1 a { font-size: 0.8rem; color: #7a5c2a; margin-left: 10px; }
    article {
      background: #fffdf8; border: 1px solid #d8ccb4; border-radius: 8px;
      padding: 12px 14px; margin-bottom: 10px;
    }
    .meta {
      display: flex; flex-wrap: wrap; justify-content: space-between; gap: 6px;
      font-size: 0.78rem; color: #7a6a4a; margin-bottom: 6px;
    }
    .meta a { color: #7a5c2a; }
    article p { margin: 0; white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.55; }
    .empty { color: #a89a7a; font-style: italic; }
  </style>
</head>
<body>
  <main>
    <h1>Messages (__COUNT__) <a href="/eval">eval &rarr;</a></h1>
    __ROWS__
  </main>
</body>
</html>
"""
