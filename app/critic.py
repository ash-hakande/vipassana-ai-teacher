import json
import logging
import re
from typing import List, Optional

from app.client import _call_agent, _create_client
from app.config import config
from app.generator import _format_context
from app.prompts import GROUNDER_SYSTEM

logger = logging.getLogger(__name__)

_FALLBACK = {
    "verdict": "APPROVED",
    "note": "Grounder response could not be parsed — returning draft as-is.",
    "revised_answer": None,
}


def _parse_json(raw: str) -> Optional[dict]:
    """Try multiple strategies to extract a JSON object from a string."""
    text = raw.strip()

    # Strip markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        text = text.strip()

    # Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # First {...} block
    match = re.search(r'\{[\s\S]*?\}', text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # Greedy match — catches nested braces
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return None


class GrounderAgent:
    def __init__(self):
        self.client = _create_client()
        self.model = config.OPENROUTER_REVIEWER_AGENT

    async def ground(self, draft: str, chunks: List[dict]) -> dict:
        system = GROUNDER_SYSTEM.format(
            context=_format_context(chunks),
            draft=draft,
        )
        raw = await _call_agent(
            client=self.client,
            agent=self.model,
            system_prompt=system,
            user_prompt="Review and ground the draft answer.",
            temperature=0.3,
            max_tokens=1024,
        )

        result = _parse_json(raw)
        if result is not None:
            return result

        logger.warning("[GrounderAgent] Could not parse JSON. model=%s raw=%r", self.model, raw[:400])
        return _FALLBACK
