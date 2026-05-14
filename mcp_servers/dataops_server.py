from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.tools.providers.sqlite_provider import SQLiteDataOpsToolProvider


TOOL_SPECS: list[dict[str, Any]] = [
    {
        "name": "query_task_runs",
        "description": "Query scheduled task runs by DAG/task, produced table, date, or status.",
    },
    {
        "name": "query_table_partitions",
        "description": "Query partition status for a table and optional business date.",
    },
    {
        "name": "query_data_volume",
        "description": "Query row count trend and anomaly information for a table.",
    },
    {
        "name": "query_null_rate",
        "description": "Query null-rate quality checks for a table field.",
    },
    {
        "name": "query_lineage",
        "description": "Query upstream or downstream table lineage.",
    },
    {
        "name": "create_incident_report",
        "description": "Persist a structured incident report and log the tool call.",
    },
]


def build_provider(database_url: str | None = None) -> SQLiteDataOpsToolProvider:
    return SQLiteDataOpsToolProvider(database_url=database_url)


def invoke_tool(
    tool_name: str,
    arguments: dict[str, Any],
    database_url: str | None = None,
) -> dict[str, Any]:
    provider = build_provider(database_url)
    tool = getattr(provider, tool_name, None)
    if tool is None or tool_name.startswith("_"):
        return {
            "tool_name": tool_name,
            "status": "failed",
            "error_message": f"Unknown tool: {tool_name}",
        }
    return tool(**arguments)


def _print_json(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def _serve_jsonl(database_url: str | None) -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            response = invoke_tool(
                str(request["tool"]),
                dict(request.get("arguments", {})),
                database_url=database_url,
            )
        except Exception as exc:
            response = {"status": "failed", "error_message": str(exc)}
        print(json.dumps(response, ensure_ascii=False), flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local DataOps MCP tool server")
    parser.add_argument("--database-url", help="Override sqlite:/// database URL")
    parser.add_argument("--tool", help="Invoke a single tool by name")
    parser.add_argument("--args", default="{}", help="JSON object with tool arguments")
    parser.add_argument(
        "--serve-jsonl",
        action="store_true",
        help="Read JSONL tool requests from stdin and write JSONL responses.",
    )
    args = parser.parse_args(argv)

    if args.serve_jsonl:
        _serve_jsonl(args.database_url)
        return 0

    if args.tool:
        tool_args = json.loads(args.args)
        if not isinstance(tool_args, dict):
            raise ValueError("--args must be a JSON object")
        _print_json(invoke_tool(args.tool, tool_args, database_url=args.database_url))
        return 0

    _print_json(
        {
            "server": "dataops-oncall-agent-tools",
            "transport": "local-json-cli",
            "tools": TOOL_SPECS,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

