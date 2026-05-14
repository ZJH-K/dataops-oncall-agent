from dataclasses import dataclass
import os
from pathlib import Path


def _load_dotenv_if_present(path: Path = Path(".env")) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv_if_present()


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "local")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///data/dataops_oncall.db")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    llm_provider: str = os.getenv("LLM_PROVIDER", "local")
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    deepseek_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
    deepseek_timeout_seconds: int = int(os.getenv("DEEPSEEK_TIMEOUT_SECONDS", "30"))
    embedding_provider: str = os.getenv("EMBEDDING_PROVIDER", "local")
    dashscope_api_key: str = os.getenv("DASHSCOPE_API_KEY", "")
    dashscope_base_url: str = os.getenv(
        "DASHSCOPE_BASE_URL",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    dashscope_embedding_model: str = os.getenv(
        "DASHSCOPE_EMBEDDING_MODEL",
        "text-embedding-v4",
    )
    dashscope_embedding_dimensions: int = int(
        os.getenv("DASHSCOPE_EMBEDDING_DIMENSIONS", "1024")
    )
    dashscope_timeout_seconds: int = int(os.getenv("DASHSCOPE_TIMEOUT_SECONDS", "30"))
    rag_embedding_weight: float = float(os.getenv("RAG_EMBEDDING_WEIGHT", "4.0"))


settings = Settings()
