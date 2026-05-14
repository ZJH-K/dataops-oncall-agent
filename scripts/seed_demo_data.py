from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db.connection import database_path, db_connection
from app.db.demo_seed import seed_demo_data


def main() -> None:
    with db_connection() as connection:
        seed_demo_data(connection)

    print(f"Seeded SQLite demo data at {database_path()}")


if __name__ == "__main__":
    main()
