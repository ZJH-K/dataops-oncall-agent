from __future__ import annotations

from pathlib import Path
from typing import Any

from app.rag.retriever import LocalRagRetriever, RagIndexNotFoundError
from app.workflow.state import DiagnosisState


def knowledge_retriever_node(
    state: DiagnosisState,
    index_path: Path,
) -> dict[str, Any]:
    skill = state.get("selected_diagnosis_skill", {})
    context = state.get("alert_context", {})
    skill_name = skill.get("name")
    table_name = context.get("table_name")
    query = " ".join(
        str(part)
        for part in [
            state.get("raw_alert", ""),
            skill_name,
            table_name,
            context.get("field_name"),
        ]
        if part
    )

    try:
        retriever = LocalRagRetriever(index_path=index_path)
        docs = retriever.search_dicts(
            query=query,
            top_k=5,
            skill_name=skill_name,
            table_name=table_name,
        )
    except RagIndexNotFoundError as exc:
        return {
            "retrieved_docs": [],
            "errors": [
                *state.get("errors", []),
                {"node": "KnowledgeRetriever", "error": str(exc)},
            ],
            "confidence_limit": "未检索到本地 RAG 索引，报告不能声称基于 Runbook。",
        }

    if retriever.embedding_error:
        return {
            "retrieved_docs": docs,
            "errors": [
                *state.get("errors", []),
                {"node": "KnowledgeRetriever", "error": retriever.embedding_error},
            ],
        }
    return {"retrieved_docs": docs}
