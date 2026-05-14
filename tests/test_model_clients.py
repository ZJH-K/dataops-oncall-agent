from __future__ import annotations

from typing import Any

import app.models.clients as clients
from app.models import AliyunEmbeddingClient, DeepSeekChatClient, cosine_similarity


def test_deepseek_chat_client_uses_openai_compatible_endpoint(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def fake_post_json(
        url: str,
        api_key: str,
        payload: dict[str, Any],
        timeout_seconds: int,
    ) -> dict[str, Any]:
        captured.update(
            {
                "url": url,
                "api_key": api_key,
                "payload": payload,
                "timeout_seconds": timeout_seconds,
            }
        )
        return {"choices": [{"message": {"content": "摘要"}}]}

    monkeypatch.setattr(clients, "_post_json", fake_post_json)

    result = DeepSeekChatClient(
        api_key="deepseek-key",
        base_url="https://api.deepseek.com",
        model="deepseek-v4-flash",
        timeout_seconds=9,
    ).complete([{"role": "user", "content": "hello"}])

    assert result == "摘要"
    assert captured["url"] == "https://api.deepseek.com/chat/completions"
    assert captured["api_key"] == "deepseek-key"
    assert captured["payload"]["model"] == "deepseek-v4-flash"
    assert captured["payload"]["stream"] is False
    assert captured["payload"]["thinking"] == {"type": "disabled"}
    assert captured["timeout_seconds"] == 9


def test_aliyun_embedding_client_uses_dashscope_compatible_endpoint(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def fake_post_json(
        url: str,
        api_key: str,
        payload: dict[str, Any],
        timeout_seconds: int,
    ) -> dict[str, Any]:
        captured.update(
            {
                "url": url,
                "api_key": api_key,
                "payload": payload,
                "timeout_seconds": timeout_seconds,
            }
        )
        return {
            "data": [
                {"index": 1, "embedding": [0.0, 1.0]},
                {"index": 0, "embedding": [1.0, 0.0]},
            ]
        }

    monkeypatch.setattr(clients, "_post_json", fake_post_json)

    embeddings = AliyunEmbeddingClient(
        api_key="dashscope-key",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model="text-embedding-v4",
        dimensions=1024,
        timeout_seconds=7,
    ).embed_texts(["query", "document"])

    assert embeddings == [[1.0, 0.0], [0.0, 1.0]]
    assert captured["url"] == "https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings"
    assert captured["api_key"] == "dashscope-key"
    assert captured["payload"]["model"] == "text-embedding-v4"
    assert captured["payload"]["dimensions"] == 1024
    assert captured["timeout_seconds"] == 7


def test_aliyun_embedding_client_batches_large_inputs(monkeypatch) -> None:
    batch_sizes: list[int] = []

    def fake_post_json(
        url: str,
        api_key: str,
        payload: dict[str, Any],
        timeout_seconds: int,
    ) -> dict[str, Any]:
        texts = payload["input"]
        batch_sizes.append(len(texts))
        return {
            "data": [
                {"index": index, "embedding": [float(index), 1.0]}
                for index, _ in enumerate(texts)
            ]
        }

    monkeypatch.setattr(clients, "_post_json", fake_post_json)

    embeddings = AliyunEmbeddingClient(
        api_key="dashscope-key",
        model="text-embedding-v4",
    ).embed_texts([f"text-{index}" for index in range(21)])

    assert batch_sizes == [10, 10, 1]
    assert len(embeddings) == 21


def test_cosine_similarity() -> None:
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0
