from __future__ import annotations

import json
import re
from typing import Any

from app.config import settings
from app.models import DeepSeekChatClient, ExternalModelError


JSON_OBJECT_PATTERN = re.compile(r"\{.*\}", re.DOTALL)


def deepseek_decision_enabled() -> bool:
    return settings.llm_provider.lower() == "deepseek" and bool(settings.deepseek_api_key)


def ask_deepseek_json(
    node: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 700,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    decision: dict[str, Any] = {
        "node": node,
        "provider": "deepseek",
        "model": settings.deepseek_model,
        "status": "skipped",
    }
    if not deepseek_decision_enabled():
        decision["reason"] = "LLM_PROVIDER is not deepseek or DEEPSEEK_API_KEY is empty."
        return None, decision

    try:
        content = DeepSeekChatClient.from_settings().complete(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens,
            temperature=0.1,
        )
        parsed = _parse_json_object(content)
    except (ExternalModelError, ValueError) as exc:
        decision.update({"status": "failed", "error": str(exc)})
        return None, decision

    decision.update({"status": "success", "parsed": parsed})
    return parsed, decision


def append_llm_decision(
    state_decisions: list[dict[str, Any]] | None,
    decision: dict[str, Any],
) -> list[dict[str, Any]]:
    if decision.get("status") == "skipped":
        return list(state_decisions or [])
    return [*list(state_decisions or []), decision]


def _parse_json_object(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.startswith("json"):
            text = text[4:].strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = JSON_OBJECT_PATTERN.search(text)
        if not match:
            raise ValueError("DeepSeek response did not contain a JSON object.")
        data = json.loads(match.group(0))

    if not isinstance(data, dict):
        raise ValueError("DeepSeek response JSON must be an object.")
    return data
