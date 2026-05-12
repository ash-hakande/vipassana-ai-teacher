import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from pydantic import BaseModel


# ── Pydantic request/response schemas ──────────────────────────────────────

class StartSessionResponse(BaseModel):
    session_id: str
    message: str
    status: str


class RespondRequest(BaseModel):
    message: str


class SourcePassage(BaseModel):
    text: str
    source: str
    chunk_id: str


class RespondResponse(BaseModel):
    session_id: str
    reply: str
    sources: List[SourcePassage]
    critic_approved: bool
    critic_note: Optional[str] = None


class EndSessionResponse(BaseModel):
    session_id: str
    status: str
    turn_count: int


class HealthResponse(BaseModel):
    status: str
    documents_indexed: int


# ── In-memory session store ─────────────────────────────────────────────────

@dataclass
class ConversationTurn:
    role: str   # "user" | "assistant"
    content: str


@dataclass
class Session:
    id: str
    history: List[ConversationTurn] = field(default_factory=list)
    status: str = "active"


_sessions: Dict[str, Session] = {}


def create_session() -> Session:
    s = Session(id=str(uuid.uuid4()))
    _sessions[s.id] = s
    return s


def get_session(session_id: str) -> Optional[Session]:
    return _sessions.get(session_id)
