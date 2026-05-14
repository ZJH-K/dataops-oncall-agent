from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class DocumentChunk:
    chunk_id: str
    content: str
    source_file: str
    doc_type: str
    section_title: str
    skill_name: str | None
    table_name: str | None
    tokens: list[str]
    embedding: list[float] | None = None
    embedding_model: str | None = None
    embedding_dimensions: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RetrievalResult:
    chunk_id: str
    content: str
    score: float
    source_file: str
    doc_type: str
    section_title: str
    skill_name: str | None
    table_name: str | None
    retrieval_mode: str = "keyword"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
