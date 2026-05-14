from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Any

from app.config import settings
from app.rag.indexer import DEFAULT_INDEX_PATH, tokenize
from app.models import AliyunEmbeddingClient, ExternalModelError, cosine_similarity
from app.rag.schemas import RetrievalResult


class RagIndexNotFoundError(FileNotFoundError):
    pass


class LocalRagRetriever:
    def __init__(
        self,
        index_path: Path = DEFAULT_INDEX_PATH,
        use_embeddings: bool | None = None,
    ) -> None:
        self.index_path = index_path
        self._chunks = self._load_chunks(index_path)
        self.embedding_error: str | None = None
        self._use_embeddings = (
            self._index_has_embeddings()
            and settings.embedding_provider.lower() == "aliyun"
            and bool(settings.dashscope_api_key)
            if use_embeddings is None
            else use_embeddings
        )

    def search(
        self,
        query: str,
        top_k: int = 5,
        skill_name: str | None = None,
        table_name: str | None = None,
        doc_type: str | None = None,
    ) -> list[RetrievalResult]:
        query_tokens = tokenize(query)
        query_counter = Counter(query_tokens)
        normalized_query = query.casefold()
        query_embedding = self._embed_query(query) if self._use_embeddings else None
        results: list[RetrievalResult] = []

        for chunk in self._chunks:
            if skill_name and chunk.get("skill_name") != skill_name:
                continue
            if table_name and chunk.get("table_name") != table_name:
                continue
            if doc_type and chunk.get("doc_type") != doc_type:
                continue

            keyword_score = self._score_chunk(chunk, query_counter, normalized_query)
            embedding_score = self._embedding_score(chunk, query_embedding)
            score = keyword_score + (embedding_score * settings.rag_embedding_weight)
            if score <= 0:
                continue
            results.append(
                RetrievalResult(
                    chunk_id=str(chunk["chunk_id"]),
                    content=str(chunk["content"]),
                    score=round(score, 4),
                    source_file=str(chunk["source_file"]),
                    doc_type=str(chunk["doc_type"]),
                    section_title=str(chunk["section_title"]),
                    skill_name=chunk.get("skill_name"),
                    table_name=chunk.get("table_name"),
                    retrieval_mode="hybrid" if query_embedding else "keyword",
                )
            )

        results.sort(
            key=lambda result: (
                result.score,
                1 if result.doc_type == "runbook" else 0,
                result.source_file,
            ),
            reverse=True,
        )
        return results[:top_k]

    def search_dicts(
        self,
        query: str,
        top_k: int = 5,
        skill_name: str | None = None,
        table_name: str | None = None,
        doc_type: str | None = None,
    ) -> list[dict[str, Any]]:
        return [
            result.to_dict()
            for result in self.search(
                query=query,
                top_k=top_k,
                skill_name=skill_name,
                table_name=table_name,
                doc_type=doc_type,
            )
        ]

    def _load_chunks(self, index_path: Path) -> list[dict[str, Any]]:
        if not index_path.exists():
            raise RagIndexNotFoundError(
                f"RAG index not found at {index_path}. Run scripts/build_rag_index.py first."
            )
        payload = json.loads(index_path.read_text(encoding="utf-8"))
        chunks = payload.get("chunks", [])
        if not isinstance(chunks, list):
            raise ValueError("RAG index chunks must be a list")
        return chunks

    def _index_has_embeddings(self) -> bool:
        return any(isinstance(chunk.get("embedding"), list) for chunk in self._chunks)

    def _embed_query(self, query: str) -> list[float] | None:
        try:
            return AliyunEmbeddingClient.from_settings().embed_query(query)
        except ExternalModelError as exc:
            self.embedding_error = str(exc)
            return None

    def _score_chunk(
        self,
        chunk: dict[str, Any],
        query_counter: Counter[str],
        normalized_query: str,
    ) -> float:
        chunk_tokens = set(chunk.get("tokens", []))
        content = str(chunk.get("content", "")).casefold()
        source_file = str(chunk.get("source_file", "")).casefold()
        section_title = str(chunk.get("section_title", "")).casefold()
        score = 0.0

        for token, count in query_counter.items():
            if token in chunk_tokens:
                score += 1.0 * count
            if token and token in content:
                score += 0.25
            if token and token in source_file:
                score += 0.35
            if token and token in section_title:
                score += 0.2

        skill_name = str(chunk.get("skill_name") or "").casefold()
        table_name = str(chunk.get("table_name") or "").casefold()
        doc_type = str(chunk.get("doc_type") or "")

        if skill_name and skill_name in normalized_query:
            score += 2.5
        if table_name and table_name in normalized_query:
            score += 2.0
        if doc_type == "runbook":
            score += 0.75
        if doc_type in {"quality_rule", "postmortem", "table"}:
            score += 0.25
        return score

    def _embedding_score(
        self,
        chunk: dict[str, Any],
        query_embedding: list[float] | None,
    ) -> float:
        if query_embedding is None:
            return 0.0
        embedding = chunk.get("embedding")
        if not isinstance(embedding, list):
            return 0.0
        return max(0.0, cosine_similarity(query_embedding, [float(value) for value in embedding]))
