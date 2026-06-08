import asyncio
import logging
from typing import Any, Dict, Optional

from openai import OpenAI

from app.config import config

logger = logging.getLogger(__name__)


def _create_client(api_key: Optional[str] = None) -> OpenAI:
    """Create OpenAI client with OpenRouter base URL."""
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key or config.OPENROUTER_API_KEY,
    )


async def _call_agent(
    client: OpenAI,
    agent: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.7,
    max_tokens: int = 1500,
    response_format: Optional[Dict[str, Any]] = None,
) -> str:
    """Call an OpenRouter agent and return the response content."""
    def create_completion():
        kwargs: Dict[str, Any] = dict(
            extra_headers={
                "HTTP-Referer": "https://vipassana-teacher.local",
                "X-Title": "Vipassana AI Assistant",
            },
            model=agent,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if response_format:
            kwargs["response_format"] = response_format
        return client.chat.completions.create(**kwargs)

    completion = await asyncio.to_thread(create_completion)
    content = completion.choices[0].message.content if completion.choices else None
    if content is None:
        finish_reason = completion.choices[0].finish_reason if completion.choices else "no choices"
        logger.warning("[_call_agent] %s returned null content (finish_reason=%s)", agent, finish_reason)
        return ""
    return content
