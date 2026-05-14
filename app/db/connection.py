from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
import sqlite3

from app.config import settings


def database_path(database_url: str | None = None) -> Path:
    url = database_url or settings.database_url
    if not url.startswith("sqlite:///"):
        raise ValueError(f"Only sqlite:/// URLs are supported, got: {url}")

    raw_path = url.removeprefix("sqlite:///")
    return Path(raw_path)


def connect(database_url: str | None = None) -> sqlite3.Connection:
    path = database_path(database_url)
    path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    return connection


@contextmanager
def db_connection(database_url: str | None = None) -> Iterator[sqlite3.Connection]:
    connection = connect(database_url)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

