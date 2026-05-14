from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.connection import db_connection
from app.db.demo_seed import seed_demo_data
from app.rag.indexer import build_rag_index
from app.rag.retriever import LocalRagRetriever
from app.skills.loader import load_builtin_skills
from app.skills.matcher import DiagnosisSkillMatcher
from app.workflow.graph import run_diagnosis


DATASET_DIR = Path(__file__).resolve().parent / "datasets"
DEFAULT_THRESHOLDS = {
    "skill_match_cases": 0.85,
    "rag_cases": 0.80,
    "tool_coverage_cases": 0.90,
}


def load_jsonl(dataset_name: str) -> list[dict[str, Any]]:
    dataset_path = DATASET_DIR / f"{dataset_name}.jsonl"
    if not dataset_path.exists():
        raise FileNotFoundError(f"dataset not found: {dataset_path}")

    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(dataset_path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            row = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{dataset_path}:{line_number}: invalid JSON") from exc
        row.setdefault("case_id", f"{dataset_name}_{line_number}")
        rows.append(row)
    if not rows:
        raise ValueError(f"dataset has no cases: {dataset_path}")
    return rows


def evaluate_skill_match_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    matcher = DiagnosisSkillMatcher(load_builtin_skills())
    details: list[dict[str, Any]] = []
    correct = 0

    for case in cases:
        result = matcher.match(str(case["input"]))
        predicted = result.skill_name
        expected = case["expected_skill"]
        passed = predicted == expected
        correct += int(passed)
        details.append(
            {
                "case_id": case["case_id"],
                "expected_skill": expected,
                "predicted_skill": predicted,
                "confidence": result.confidence,
                "passed": passed,
            }
        )

    accuracy = correct / len(cases)
    return {
        "dataset": "skill_match_cases",
        "metric_name": "accuracy",
        "metric_value": round(accuracy, 4),
        "total": len(cases),
        "passed": correct,
        "failed": len(cases) - correct,
        "details": details,
    }


def evaluate_rag_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    details: list[dict[str, Any]] = []
    hits = 0

    with TemporaryDirectory(prefix="dataops_rag_eval_") as temp_dir:
        index_path = Path(temp_dir) / "rag_index.json"
        build_rag_index(index_path=index_path)
        retriever = LocalRagRetriever(index_path=index_path)

        for case in cases:
            filters = dict(case.get("filters") or {})
            results = retriever.search(
                query=str(case["input"]),
                top_k=int(case.get("top_k", 3)),
                skill_name=filters.get("skill_name"),
                table_name=filters.get("table_name"),
                doc_type=filters.get("doc_type"),
            )
            sources = [result.source_file for result in results]
            expected_sources = list(case["expected_sources"])
            passed = any(source in sources for source in expected_sources)
            hits += int(passed)
            details.append(
                {
                    "case_id": case["case_id"],
                    "expected_sources": expected_sources,
                    "retrieved_sources": sources,
                    "passed": passed,
                }
            )

    hit_rate = hits / len(cases)
    return {
        "dataset": "rag_cases",
        "metric_name": "hit_rate",
        "metric_value": round(hit_rate, 4),
        "total": len(cases),
        "passed": hits,
        "failed": len(cases) - hits,
        "details": details,
    }


def evaluate_tool_coverage_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    details: list[dict[str, Any]] = []
    covered_tool_count = 0
    required_tool_count = 0
    fully_covered_cases = 0

    with TemporaryDirectory(prefix="dataops_tool_eval_") as temp_dir:
        db_url = f"sqlite:///{Path(temp_dir) / 'eval.db'}"
        index_path = Path(temp_dir) / "rag_index.json"
        with db_connection(db_url) as connection:
            seed_demo_data(connection)
        build_rag_index(index_path=index_path)

        for index, case in enumerate(cases, start=1):
            state = run_diagnosis(
                raw_alert=str(case["input"]),
                session_id=f"eval-tool-{index}",
                database_url=db_url,
                index_path=index_path,
            )
            successful_tools = {
                call.get("tool_name")
                for call in state.get("tool_calls", [])
                if call.get("status") == "success"
            }
            required_tools = list(case["required_tools"])
            covered = [tool for tool in required_tools if tool in successful_tools]
            missing = [tool for tool in required_tools if tool not in successful_tools]
            required_tool_count += len(required_tools)
            covered_tool_count += len(covered)
            fully_covered_cases += int(not missing)
            details.append(
                {
                    "case_id": case["case_id"],
                    "expected_skill": case.get("expected_skill"),
                    "predicted_skill": state.get("selected_diagnosis_skill", {}).get("name"),
                    "required_tools": required_tools,
                    "successful_tools": sorted(tool for tool in successful_tools if tool),
                    "missing_tools": missing,
                    "coverage_ratio": round(len(covered) / len(required_tools), 4),
                    "passed": not missing,
                }
            )

    tool_coverage = covered_tool_count / required_tool_count
    return {
        "dataset": "tool_coverage_cases",
        "metric_name": "tool_coverage",
        "metric_value": round(tool_coverage, 4),
        "total": len(cases),
        "passed": fully_covered_cases,
        "failed": len(cases) - fully_covered_cases,
        "details": details,
    }


def evaluate_dataset(dataset_name: str) -> dict[str, Any]:
    cases = load_jsonl(dataset_name)
    if dataset_name == "skill_match_cases":
        return evaluate_skill_match_cases(cases)
    if dataset_name == "rag_cases":
        return evaluate_rag_cases(cases)
    if dataset_name == "tool_coverage_cases":
        return evaluate_tool_coverage_cases(cases)
    raise ValueError(
        "unsupported dataset. Expected one of: "
        + ", ".join(sorted(DEFAULT_THRESHOLDS))
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run DataOps OnCall Agent eval datasets.")
    parser.add_argument(
        "--dataset",
        required=True,
        choices=sorted(DEFAULT_THRESHOLDS),
        help="Dataset name without .jsonl suffix.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Override the default pass threshold for the selected metric.",
    )
    args = parser.parse_args()

    result = evaluate_dataset(args.dataset)
    threshold = args.threshold if args.threshold is not None else DEFAULT_THRESHOLDS[args.dataset]
    result["threshold"] = threshold
    result["passed_threshold"] = result["metric_value"] >= threshold

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed_threshold"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
