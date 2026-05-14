from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any

import yaml

from app.config import settings
from app.models import AliyunEmbeddingClient
from app.rag.schemas import DocumentChunk


DEFAULT_DOCS_DIR = Path("docs")
DEFAULT_INDEX_PATH = Path("data/rag_index.json")
RAG_DOC_DIRS = {
    "runbooks": "runbook",
    "tables": "table",
    "postmortems": "postmortem",
    "quality_rules": "quality_rule",
}

FRONT_MATTER_PATTERN = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
ASCII_TOKEN_PATTERN = re.compile(r"[a-z0-9_]+(?:\.[a-z0-9_]+)?")
CJK_SEQUENCE_PATTERN = re.compile(r"[\u4e00-\u9fff]{2,}")


def tokenize(text: str) -> list[str]:
    normalized = text.casefold()
    tokens = ASCII_TOKEN_PATTERN.findall(normalized)
    for sequence in CJK_SEQUENCE_PATTERN.findall(normalized):
        tokens.append(sequence)
        for size in (2, 3, 4):
            tokens.extend(
                sequence[index : index + size]
                for index in range(0, max(len(sequence) - size + 1, 0))
            )
    return tokens


def parse_markdown_file(path: Path, docs_dir: Path = DEFAULT_DOCS_DIR) -> list[DocumentChunk]:
    raw_text = path.read_text(encoding="utf-8")
    metadata, body = _split_front_matter(raw_text)
    doc_type = str(
        metadata.get("doc_type")
        or RAG_DOC_DIRS.get(path.parent.name)
        or "document"
    )
    skill_name = _optional_text(metadata.get("skill_name"))
    table_name = _optional_text(metadata.get("table_name"))
    source_file = path.as_posix()

    chunks: list[DocumentChunk] = []
    for index, (section_title, content) in enumerate(_split_sections(body), start=1):
        chunk_content = content.strip()
        if not chunk_content:
            continue
        chunk_id = f"{path.relative_to(docs_dir).with_suffix('').as_posix()}#{index}"
        token_text = " ".join(
            part
            for part in [
                chunk_content,
                doc_type,
                section_title,
                skill_name,
                table_name,
                path.stem,
            ]
            if part
        )
        chunks.append(
            DocumentChunk(
                chunk_id=chunk_id,
                content=chunk_content,
                source_file=source_file,
                doc_type=doc_type,
                section_title=section_title,
                skill_name=skill_name,
                table_name=table_name,
                tokens=sorted(set(tokenize(token_text))),
            )
        )
    return chunks


def build_rag_index(
    docs_dir: Path = DEFAULT_DOCS_DIR,
    index_path: Path = DEFAULT_INDEX_PATH,
    embedding_provider: str | None = None,
) -> dict[str, Any]:
    chunks: list[DocumentChunk] = []
    for dirname in RAG_DOC_DIRS:
        source_dir = docs_dir / dirname
        if not source_dir.exists():
            continue
        for path in sorted(source_dir.glob("*.md")):
            chunks.extend(parse_markdown_file(path, docs_dir))

    resolved_embedding_provider = (embedding_provider or settings.embedding_provider).lower()
    embedding_model = None
    embedding_dimensions = None
    if resolved_embedding_provider == "aliyun" and chunks:
        embedding_client = AliyunEmbeddingClient.from_settings()
        embeddings = embedding_client.embed_texts([_embedding_text(chunk) for chunk in chunks])
        chunks = [
            DocumentChunk(
                chunk_id=chunk.chunk_id,
                content=chunk.content,
                source_file=chunk.source_file,
                doc_type=chunk.doc_type,
                section_title=chunk.section_title,
                skill_name=chunk.skill_name,
                table_name=chunk.table_name,
                tokens=chunk.tokens,
                embedding=embedding,
                embedding_model=embedding_client.model,
                embedding_dimensions=len(embedding),
            )
            for chunk, embedding in zip(chunks, embeddings, strict=True)
        ]
        embedding_model = embedding_client.model
        embedding_dimensions = embedding_client.dimensions

    payload = {
        "version": 1,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "chunk_count": len(chunks),
        "embedding_provider": resolved_embedding_provider,
        "embedding_model": embedding_model,
        "embedding_dimensions": embedding_dimensions,
        "chunks": [chunk.to_dict() for chunk in chunks],
    }

    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return payload


def _split_front_matter(raw_text: str) -> tuple[dict[str, Any], str]:
    match = FRONT_MATTER_PATTERN.match(raw_text)
    if not match:
        return {}, raw_text
    metadata = yaml.safe_load(match.group(1)) or {}
    if not isinstance(metadata, dict):
        raise ValueError("front matter must be a YAML object")
    return metadata, raw_text[match.end() :]


def _split_sections(body: str) -> list[tuple[str, str]]:
    matches = list(HEADING_PATTERN.finditer(body))
    if not matches:
        return [("Document", body)]

    sections: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        section_title = match.group(2).strip()
        sections.append((section_title, body[start:end].strip()))
    return sections


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _embedding_text(chunk: DocumentChunk) -> str:
    metadata = [
        f"doc_type={chunk.doc_type}",
        f"source_file={chunk.source_file}",
        f"section_title={chunk.section_title}",
    ]
    if chunk.skill_name:
        metadata.append(f"skill_name={chunk.skill_name}")
    if chunk.table_name:
        metadata.append(f"table_name={chunk.table_name}")
    return "\n".join([*metadata, "", chunk.content])
