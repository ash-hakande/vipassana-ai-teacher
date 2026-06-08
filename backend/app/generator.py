from typing import List

from app.client import _call_agent, _create_client
from app.config import config
from app.prompts import GENERATOR_SYSTEM


def _format_context(chunks: List[dict]) -> str:
    if not chunks:
        return "(No relevant passages found in the documents.)"
    lines = []
    for c in chunks:
        label = c.get("citation") or c["source"]
        lines.append(f"[{label}]\n{c['text']}")
    return "\n\n".join(lines)


def _format_history(history: List[dict]) -> str:
    if not history:
        return "(No prior conversation.)"
    lines = []
    for turn in history:
        role = "STUDENT" if turn["role"] == "user" else "TEACHER"
        lines.append(f"{role}: {turn['content']}")
    return "\n".join(lines)


class GeneratorAgent:
    def __init__(self):
        self.client = _create_client()
        self.model = config.OPENROUTER_GENERATOR_AGENT

    async def generate(
        self,
        question: str,
        chunks: List[dict],
        history: List[dict],
    ) -> str:
        system = GENERATOR_SYSTEM.format(
            context=_format_context(chunks),
            history=_format_history(history),
        )
        return await _call_agent(
            client=self.client,
            agent=self.model,
            system_prompt=system,
            user_prompt=question,
            temperature=0.7,
            max_tokens=1024,
        )
