from pathlib import Path
import argparse
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.rag.indexer import DEFAULT_INDEX_PATH, build_rag_index


def main() -> None:
    parser = argparse.ArgumentParser(description="Build local RAG index.")
    parser.add_argument(
        "--embedding-provider",
        choices=["local", "aliyun"],
        default=None,
        help="Use aliyun to persist text-embedding-v4 vectors in the index.",
    )
    args = parser.parse_args()
    payload = build_rag_index(embedding_provider=args.embedding_provider)
    embedding = payload.get("embedding_provider")
    model = payload.get("embedding_model") or "none"
    print(
        f"Built RAG index at {DEFAULT_INDEX_PATH} with {payload['chunk_count']} chunks "
        f"(embedding_provider={embedding}, embedding_model={model})"
    )


if __name__ == "__main__":
    main()
