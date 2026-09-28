import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


# ── Pydantic request/response schemas ──────────────────────────────────────

class StartSessionResponse(BaseModel):
    session_id: str
    message: str
    status: str


class RespondRequest(BaseModel):
    message: str


class ContactRequest(BaseModel):
    message: str = Field(min_length=1, max_length=5000)
    name: str = Field(default="", max_length=200)
    email: str = Field(default="", max_length=200)
    # Honeypot: hidden in the form, so only bots fill it in
    website: str = ""


class SourcePassage(BaseModel):
    text: str
    source: str
    chunk_id: str
    citation: str = ""
    url: str = ""
    page: int = -1


class RespondResponse(BaseModel):
    session_id: str
    reply: str
    sources: List[SourcePassage]
    critic_approved: bool
    critic_note: Optional[str] = None


class EvalConfig(BaseModel):
    model: str
    top_k: int = 5


class EvalRequest(BaseModel):
    question: str
    configs: List[EvalConfig]


class EvalRunResult(BaseModel):
    config: EvalConfig
    reply: str
    sources: List[SourcePassage]
    critic_approved: bool
    critic_note: Optional[str] = None
    latency_ms: int = 0
    error: Optional[str] = None


class EvalResponse(BaseModel):
    question: str
    results: List[EvalRunResult]


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
