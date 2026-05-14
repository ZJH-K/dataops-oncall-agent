from __future__ import annotations

import json
import math
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.config import settings


class ExternalModelError(RuntimeError):
    pass


class DeepSeekChatClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-v4-flash",
        timeout_seconds: int = 30,
    ) -> None:
        if not api_key:
            raise ExternalModelError("DEEPSEEK_API_KEY is required when LLM_PROVIDER=deepseek.")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    @classmethod
    def from_settings(cls) -> DeepSeekChatClient:
        return cls(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            model=settings.deepseek_model,
            timeout_seconds=settings.deepseek_timeout_seconds,
        )

    def complete(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 600,
        temperature: float = 0.2,
    ) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
            "thinking": {"type": "disabled"},
        }
        data = _post_json(
            url=f"{self.base_url}/chat/completions",
            api_key=self.api_key,
            payload=payload,
            timeout_seconds=self.timeout_seconds,
        )
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ExternalModelError("DeepSeek response missing choices.")
        message = choices[0].get("message", {})
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            finish_reason = choices[0].get("finish_reason")
            raise ExternalModelError(
                "DeepSeek response missing message content "
                f"(finish_reason={finish_reason})."
            )
        return content.strip()


class AliyunEmbeddingClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1",
        model: str = "text-embedding-v4",
        dimensions: int = 1024,
        timeout_seconds: int = 30,
    ) -> None:
        if not api_key:
            raise ExternalModelError(
                "DASHSCOPE_API_KEY is required when EMBEDDING_PROVIDER=aliyun."
            )
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.dimensions = dimensions
        self.timeout_seconds = timeout_seconds

    @classmethod
    def from_settings(cls) -> AliyunEmbeddingClient:
        return cls(
            api_key=settings.dashscope_api_key,
            base_url=settings.dashscope_base_url,
            model=settings.dashscope_embedding_model,
            dimensions=settings.dashscope_embedding_dimensions,
            timeout_seconds=settings.dashscope_timeout_seconds,
        )

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        embeddings: list[list[float]] = []
        for start in range(0, len(texts), 10):
            embeddings.extend(self._embed_batch(texts[start : start + 10]))
        return embeddings

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        payload: dict[str, Any] = {
            "model": self.model,
            "input": texts,
            "dimensions": self.dimensions,
        }
        data = _post_json(
            url=f"{self.base_url}/embeddings",
            api_key=self.api_key,
            payload=payload,
            timeout_seconds=self.timeout_seconds,
        )
        items = data.get("data")
        if not isinstance(items, list):
            raise ExternalModelError("DashScope embedding response missing data.")
        items.sort(key=lambda item: int(item.get("index", 0)))
        embeddings: list[list[float]] = []
        for item in items:
            embedding = item.get("embedding")
            if not isinstance(embedding, list):
                raise ExternalModelError("DashScope embedding item missing embedding.")
            embeddings.append([float(value) for value in embedding])
        if len(embeddings) != len(texts):
            raise ExternalModelError("DashScope embedding response count mismatch.")
        return embeddings

    def embed_query(self, query: str) -> list[float]:
        return self.embed_texts([query])[0]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)


def _post_json(
    url: str,
    api_key: str,
    payload: dict[str, Any],
    timeout_seconds: int,
) -> dict[str, Any]:
    request = Request(
        url=url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            raw_body = response.read().decode("utf-8")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise ExternalModelError(f"HTTP {exc.code} from {url}: {_safe_error_body(body)}") from exc
    except URLError as exc:
        raise ExternalModelError(f"Failed to call {url}: {exc.reason}") from exc

    try:
        data = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise ExternalModelError(f"Invalid JSON response from {url}.") from exc
    if not isinstance(data, dict):
        raise ExternalModelError(f"Unexpected JSON response from {url}.")
    return data


def _safe_error_body(body: str) -> str:
    compact = " ".join(body.split())
    return compact[:500]
