import asyncio
import time
from typing import List

from app.client import _call_agent, _create_client
from app.critic import GrounderAgent
from app.generator import _format_context, _format_history
from app.models import EvalConfig, EvalRunResult, SourcePassage
from app.prompts import GENERATOR_SYSTEM
from app.retriever import RetrieverAgent


async def run_eval_config(
    question: str,
    cfg: EvalConfig,
    retriever: RetrieverAgent,
    grounder: GrounderAgent,
) -> EvalRunResult:
    start = time.monotonic()
    try:
        chunks = await asyncio.to_thread(retriever.retrieve, question, cfg.top_k)
        system = GENERATOR_SYSTEM.format(
            context=_format_context(chunks),
            history=_format_history([]),
        )
        client = _create_client()
        draft = await _call_agent(
            client=client,
            agent=cfg.model,
            system_prompt=system,
            user_prompt=question,
            temperature=0.7,
            max_tokens=1024,
        )
        verdict_data = await grounder.ground(draft=draft, chunks=chunks)
        verdict = verdict_data.get("verdict", "APPROVED")
        final_reply = (verdict_data.get("revised_answer") or draft) if verdict == "ENRICHED" else draft
        return EvalRunResult(
            config=cfg,
            reply=final_reply,
            sources=[
                SourcePassage(
                    text=c["text"],
                    source=c["source"],
                    chunk_id=c["chunk_id"],
                    citation=c.get("citation", ""),
                    url=c.get("url", ""),
                    page=c.get("page", -1),
                )
                for c in chunks
            ],
            critic_approved=verdict != "REFUSED",
            critic_note=verdict_data.get("note"),
            latency_ms=round((time.monotonic() - start) * 1000),
        )
    except Exception as e:
        return EvalRunResult(
            config=cfg,
            reply="",
            sources=[],
            critic_approved=False,
            error=str(e),
            latency_ms=round((time.monotonic() - start) * 1000),
        )
