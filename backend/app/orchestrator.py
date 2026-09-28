import asyncio
import logging

from app.critic import GrounderAgent
from app.generator import GeneratorAgent
from app.models import ConversationTurn, get_session
from app.retriever import RetrieverAgent

logger = logging.getLogger(__name__)


class Orchestrator:
    def __init__(self):
        self.retriever = RetrieverAgent()
        self.generator = GeneratorAgent()
        self.grounder = GrounderAgent()

    async def respond(self, session_id: str, user_message: str) -> dict:
        session = get_session(session_id)
        if session is None:
            raise ValueError(f"Session {session_id} not found")

        # Agent 1 — Retrieve relevant document passages
        chunks = await asyncio.to_thread(self.retriever.retrieve, user_message)
        logger.info("[retriever] query=%r  chunks_found=%d", user_message[:80], len(chunks))
        for i, c in enumerate(chunks, 1):
            logger.info("  chunk %d | source=%s | distance=%.4f | preview=%r",
                        i, c["source"], c["distance"], c["text"][:80])

        # Agent 2 — Generate answer from Vipassana knowledge + document context
        history_dicts = [
            {"role": t.role, "content": t.content} for t in session.history
        ]
        draft = await self.generator.generate(
            question=user_message,
            chunks=chunks,
            history=history_dicts,
        )
        logger.info("[generator] model=%s  draft=%r", self.generator.model, draft[:120])

        # Agent 3 — Ground the answer with document citations
        verdict_data = await self.grounder.ground(draft=draft, chunks=chunks)
        verdict = verdict_data.get("verdict", "APPROVED")
        logger.info("[grounder] model=%s  verdict=%s  note=%r",
                    self.grounder.model, verdict, verdict_data.get("note"))

        if verdict == "ENRICHED":
            final_reply = verdict_data.get("revised_answer") or draft
            grounded = True
            note = verdict_data.get("note")
        else:
            # APPROVED or unrecognised — return draft as-is
            final_reply = draft
            grounded = True
            note = None

        session.history.append(ConversationTurn(role="user", content=user_message))
        session.history.append(ConversationTurn(role="assistant", content=final_reply))

        return {
            "session_id": session_id,
            "reply": final_reply,
            "sources": [
                {
                    "text": c["text"],
                    "source": c["source"],
                    "chunk_id": c["chunk_id"],
                    "citation": c.get("citation", ""),
                    "url": c.get("url", ""),
                }
                for c in chunks
            ],
            "critic_approved": grounded,
            "critic_note": note,
        }
