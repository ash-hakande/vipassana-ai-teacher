import logging

import asyncio

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app.config import Config, config
from app.models import (
    EndSessionResponse,
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
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

_orchestrator: Orchestrator = None


@app.on_event("startup")
async def startup():
    global _orchestrator
    Config.validate()
    _orchestrator = Orchestrator()
    logger.info("Vipassana AI Assistant started on port %s", config.PORT)


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


@app.get("/", response_class=HTMLResponse)
async def demo_ui():
    return HTMLResponse(content=_DEMO_HTML)


# ── Demo UI ────────────────────────────────────────────────────────────────

_DEMO_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Vipassana AI Assistant</title>
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/dompurify@3/dist/purify.min.js"></script>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: Georgia, 'Times New Roman', serif;
      background: #f5f0e8;
      color: #2c2417;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 20px 16px;
    }
    .container { width: 100%; max-width: 900px; }
    header { text-align: center; margin-bottom: 16px; }
    header h1 {
      font-size: 1.4rem;
      font-weight: normal;
      letter-spacing: 0.05em;
      color: #5a4a2a;
      border-bottom: 1px solid #c8b896;
      padding-bottom: 10px;
    }
    header p { font-size: 0.82rem; color: #8a7a5a; margin-top: 5px; }
    #chat-window {
      background: #fff;
      border: 1px solid #d8ccb4;
      border-radius: 6px;
      height: calc(100vh - 210px);
      min-height: 400px;
      overflow-y: auto;
      padding: 20px;
      margin-bottom: 12px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    .msg { display: flex; flex-direction: column; max-width: 88%; }
    .msg.user { align-self: flex-end; align-items: flex-end; }
    .msg.ai   { align-self: flex-start; align-items: flex-start; }
    .bubble {
      padding: 10px 14px;
      border-radius: 12px;
      line-height: 1.55;
      font-size: 0.875rem;
      white-space: pre-wrap;
    }
    .msg.user .bubble { background: #d4e8f7; color: #1a2a3a; border-bottom-right-radius: 3px; }
    .msg.ai   .bubble { background: #f0ebe0; color: #2c2417; border-bottom-left-radius: 3px; }
    .msg.ai.refused .bubble { background: #fdecea; color: #8b2b2b; font-style: italic; }
    .sources {
      font-size: 0.72rem;
      color: #9a8a6a;
      margin-top: 4px;
      padding-left: 6px;
      border-left: 2px solid #c8b896;
    }
    .sources a { color: #7a5c2a; text-decoration: underline; }
    .citation { color: #8b5e2a; font-style: italic; font-size: 0.88em; }
    .critic-note {
      font-size: 0.72rem;
      color: #b07040;
      margin-top: 3px;
      font-style: italic;
    }
    .input-row {
      display: flex;
      gap: 8px;
      align-items: flex-end;
    }
    textarea {
      flex: 1;
      padding: 10px 14px;
      border: 1px solid #c8b896;
      border-radius: 6px;
      font-family: inherit;
      font-size: 0.95rem;
      resize: none;
      background: #fff;
      color: #2c2417;
      line-height: 1.4;
    }
    textarea:focus { outline: none; border-color: #8a6a30; }
    button {
      padding: 10px 20px;
      background: #7a5c2a;
      color: #fff;
      border: none;
      border-radius: 6px;
      font-family: inherit;
      font-size: 0.95rem;
      cursor: pointer;
      white-space: nowrap;
      height: 42px;
    }
    button:hover { background: #5a3c10; }
    button:disabled { background: #b8a888; cursor: not-allowed; }
    #status {
      font-size: 0.78rem;
      color: #9a8a6a;
      margin-top: 8px;
      text-align: center;
      min-height: 1.2em;
    }
    .thinking { opacity: 0.6; font-style: italic; }
    /* markdown prose inside AI bubbles */
    .msg.ai .bubble p { margin: 0 0 0.6em; }
    .msg.ai .bubble p:last-child { margin-bottom: 0; }
    .msg.ai .bubble ul, .msg.ai .bubble ol { padding-left: 1.4em; margin: 0 0 0.6em; }
    .msg.ai .bubble li { margin-bottom: 0.2em; }
    .msg.ai .bubble strong { font-weight: 700; }
    .msg.ai .bubble em { font-style: italic; }
    .msg.ai .bubble h1, .msg.ai .bubble h2, .msg.ai .bubble h3 {
      font-size: 0.875rem; font-weight: 700; margin: 0.7em 0 0.3em;
    }
    .msg.ai .bubble code {
      font-family: monospace; background: #e8e0d0; padding: 1px 4px; border-radius: 3px;
    }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>Vipassana AI Assistant</h1>
      <p>Answers grounded in the provided teaching documents. AI can make mistakes — always verify with a qualified teacher.</p>
    </header>
    <div id="chat-window"></div>
    <div class="input-row">
      <textarea id="user-input" rows="2"
        placeholder="Ask about Vipassana practice, technique, or teachings..."></textarea>
      <button id="send-btn" onclick="sendMessage()">Ask</button>
    </div>
    <div id="status">Starting session...</div>
  </div>

  <script>
    let sessionId = null;

    async function init() {
      try {
        const res = await fetch('/session/start', { method: 'POST' });
        const data = await res.json();
        sessionId = data.session_id;
        appendAI(data.message, [], true, null);
        setStatus('Ready — ' + sessionId.slice(0, 8) + '...');
      } catch (e) {
        setStatus('Error starting session: ' + e.message);
      }
    }

    async function sendMessage() {
      const input = document.getElementById('user-input');
      const msg = input.value.trim();
      if (!msg || !sessionId) return;
      input.value = '';

      appendUser(msg);
      const btn = document.getElementById('send-btn');
      btn.disabled = true;
      setStatus('Consulting the teachings...');

      // Show thinking indicator
      const thinkingId = appendThinking();

      try {
        const res = await fetch('/session/' + sessionId + '/respond', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: msg }),
        });
        removeThinking(thinkingId);
        const data = await res.json();
        appendAI(data.reply, data.sources, data.critic_approved, data.critic_note);
        setStatus(data.critic_note ? 'Note: ' + data.critic_note : 'Ready');
      } catch (e) {
        removeThinking(thinkingId);
        appendAI('An error occurred: ' + e.message, [], false, null);
        setStatus('Error');
      } finally {
        btn.disabled = false;
      }
    }

    function appendUser(text) {
      const win = document.getElementById('chat-window');
      const div = document.createElement('div');
      div.className = 'msg user';
      const bubble = document.createElement('div');
      bubble.className = 'bubble';
      bubble.textContent = text;
      div.appendChild(bubble);
      win.appendChild(div);
      win.scrollTop = win.scrollHeight;
    }

    function appendAI(text, sources, approved, note) {
      const win = document.getElementById('chat-window');
      const div = document.createElement('div');
      div.className = 'msg ai' + (approved === false ? ' refused' : '');
      const bubble = document.createElement('div');
      bubble.className = 'bubble';
      const md = marked.parse(text).replace(
        /\[([^\]<>]+)\]/g,
        '<span class="citation">[$1]</span>'
      );
      bubble.innerHTML = DOMPurify.sanitize(md);
      div.appendChild(bubble);

      if (sources && sources.length) {
        const seen = new Set();
        const unique = sources.filter(s => {
          const key = s.citation || s.source;
          if (seen.has(key)) return false;
          seen.add(key); return true;
        });
        const src = document.createElement('div');
        src.className = 'sources';
        src.innerHTML = 'Sources: ' + unique.map(s => {
          const label = s.citation || s.source;
          return s.url
            ? `<a href="${s.url}" target="_blank" rel="noopener noreferrer">${label}</a>`
            : label;
        }).join(' &middot; ');
        div.appendChild(src);
      }
      if (note) {
        const n = document.createElement('div');
        n.className = 'critic-note';
        n.textContent = 'Critic: ' + note;
        div.appendChild(n);
      }
      win.appendChild(div);
      win.scrollTop = win.scrollHeight;
    }

    let _thinkingCounter = 0;
    function appendThinking() {
      const win = document.getElementById('chat-window');
      const id = 'thinking-' + (++_thinkingCounter);
      const div = document.createElement('div');
      div.className = 'msg ai';
      div.id = id;
      const bubble = document.createElement('div');
      bubble.className = 'bubble thinking';
      bubble.textContent = '...';
      div.appendChild(bubble);
      win.appendChild(div);
      win.scrollTop = win.scrollHeight;
      return id;
    }

    function removeThinking(id) {
      const el = document.getElementById(id);
      if (el) el.remove();
    }

    function setStatus(msg) {
      document.getElementById('status').textContent = msg;
    }

    document.getElementById('user-input').addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });

    init();
  </script>
</body>
</html>
"""
