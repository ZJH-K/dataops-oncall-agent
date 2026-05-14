from pathlib import Path

import app.rag.indexer as indexer
from app.rag.indexer import build_rag_index
from app.rag.retriever import LocalRagRetriever


def _build_test_retriever(tmp_path: Path) -> LocalRagRetriever:
    index_path = tmp_path / "rag_index.json"
    payload = build_rag_index(index_path=index_path)
    assert payload["chunk_count"] > 0
    return LocalRagRetriever(index_path=index_path)


def test_rag_index_chunks_have_required_metadata(tmp_path: Path) -> None:
    index_path = tmp_path / "rag_index.json"
    payload = build_rag_index(index_path=index_path)
    chunk = payload["chunks"][0]

    assert {
        "source_file",
        "doc_type",
        "section_title",
        "skill_name",
        "table_name",
        "chunk_id",
    }.issubset(chunk)


def test_data_volume_drop_query_recalls_runbook_in_top_3(tmp_path: Path) -> None:
    retriever = _build_test_retriever(tmp_path)

    results = retriever.search(
        "dws_sales_daily 今日数据量较昨日下降 92%，请判断是否存在数据事故。",
        top_k=3,
    )

    sources = {result.source_file for result in results}
    assert "docs/runbooks/data_volume_drop.md" in sources


def test_null_rate_query_recalls_null_rate_documents_in_top_3(tmp_path: Path) -> None:
    retriever = _build_test_retriever(tmp_path)

    results = retriever.search(
        "ads_user_profile 表中 user_id 字段空值率突然升高，请分析影响范围。",
        top_k=3,
    )

    sources = {result.source_file for result in results}
    assert "docs/runbooks/null_rate_spike.md" in sources
    assert sources & {
        "docs/quality_rules/null_rate_check.md",
        "docs/tables/ads_user_profile.md",
        "docs/postmortems/user_identity_null_spike_2026_05.md",
    }


def test_metadata_filters_limit_results(tmp_path: Path) -> None:
    retriever = _build_test_retriever(tmp_path)

    results = retriever.search(
        "数据量下降 row count drop",
        top_k=5,
        skill_name="data_volume_drop",
        table_name="dws_sales_daily",
    )

    assert results
    assert all(result.skill_name == "data_volume_drop" for result in results)
    assert all(result.table_name == "dws_sales_daily" for result in results)


def test_rag_index_can_store_aliyun_embeddings(
    tmp_path: Path,
    monkeypatch,
) -> None:
    class FakeEmbeddingClient:
        model = "text-embedding-v4"
        dimensions = 2

        def embed_texts(self, texts: list[str]) -> list[list[float]]:
            return [[float(index), 1.0] for index, _ in enumerate(texts)]

    monkeypatch.setattr(
        indexer.AliyunEmbeddingClient,
        "from_settings",
        lambda: FakeEmbeddingClient(),
    )

    payload = build_rag_index(
        index_path=tmp_path / "rag_index.json",
        embedding_provider="aliyun",
    )
    chunk = payload["chunks"][0]

    assert payload["embedding_provider"] == "aliyun"
    assert payload["embedding_model"] == "text-embedding-v4"
    assert chunk["embedding_model"] == "text-embedding-v4"
    assert chunk["embedding_dimensions"] == 2
    assert isinstance(chunk["embedding"], list)
