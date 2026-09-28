import logging

import asyncio

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

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
    allow_origins=Config.cors_origins(),
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

