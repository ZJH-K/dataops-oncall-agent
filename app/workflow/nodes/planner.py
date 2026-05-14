from __future__ import annotations

from typing import Any

from app.workflow.llm_decisions import append_llm_decision, ask_deepseek_json
from app.workflow.state import DEMO_LOOKBACK_START_DATE, DiagnosisState


def planner_node(state: DiagnosisState) -> dict[str, Any]:
    skill = state.get("selected_diagnosis_skill", {})
    context = state.get("alert_context", {})
    skill_name = str(skill.get("name", ""))
    required_tools = list(skill.get("required_tools", []))
    deterministic_plan = [
        _plan_step(tool_name, skill_name, context)
        for tool_name in required_tools
    ]
    llm_plan, llm_decision = _plan_with_deepseek(state, deterministic_plan)
    plan = _merge_llm_plan(
        deterministic_plan=deterministic_plan,
        llm_plan=llm_plan,
        required_tools=required_tools,
    )
    return {
        "plan": plan,
        "pending_tools": [],
        "llm_decisions": append_llm_decision(state.get("llm_decisions"), llm_decision),
    }


def plan_step_for_tool(
    tool_name: str,
    state: DiagnosisState,
) -> dict[str, Any]:
    skill = state.get("selected_diagnosis_skill", {})
    return _plan_step(tool_name, str(skill.get("name", "")), state.get("alert_context", {}))


def _plan_step(
    tool_name: str,
    skill_name: str,
    context: dict[str, Any],
) -> dict[str, Any]:
    table_name = context.get("table_name")
    task_name = context.get("task_name")
    date = context.get("biz_date")
    field_name = context.get("field_name")

    if tool_name == "query_data_volume":
        arguments = {
            "table_name": table_name,
            "start_date": DEMO_LOOKBACK_START_DATE,
            "end_date": date,
        }
        purpose = "查询目标表近期数据量趋势和异常比例"
    elif tool_name == "query_task_runs":
        arguments = {"date": date}
        if skill_name == "airflow_task_failed":
            arguments["task_name"] = task_name
        elif skill_name in {"partition_missing", "null_rate_spike"}:
            arguments["table_name"] = table_name
        elif skill_name == "data_volume_drop":
            arguments["status"] = "failed"
        purpose = "查询相关任务运行状态和失败原因"
    elif tool_name == "query_table_partitions":
        arguments = {"table_name": table_name, "date": date}
        purpose = "查询目标表当前业务日期分区状态"
    elif tool_name == "query_null_rate":
        arguments = {
            "table_name": table_name,
            "field_name": field_name,
            "start_date": DEMO_LOOKBACK_START_DATE,
            "end_date": date,
        }
        purpose = "查询字段空值率趋势和质量阈值"
    elif tool_name == "query_lineage":
        direction = "both" if skill_name in {"data_volume_drop", "partition_missing"} else "downstream"
        arguments = {"table_name": table_name, "direction": direction, "depth": 3}
        purpose = "查询上下游血缘和影响范围"
    else:
        arguments = {}
        purpose = "执行诊断工具"

    return {
        "tool_name": tool_name,
        "arguments": arguments,
        "purpose": purpose,
    }


def _plan_with_deepseek(
    state: DiagnosisState,
    deterministic_plan: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    return ask_deepseek_json(
        node="Planner",
        system_prompt=(
            "你是 DataOps 诊断计划生成器。只返回 JSON，不要解释。"
            "只能使用 deterministic_plan 里已有的 tool_name，不要创造工具。"
            "每个 plan step 必须包含 tool_name, purpose, arguments。"
            "arguments 只能填诊断需要的简单 JSON 值。"
        ),
        user_prompt=(
            f"selected_diagnosis_skill={state.get('selected_diagnosis_skill', {})}\n"
            f"alert_context={state.get('alert_context', {})}\n"
            f"retrieved_docs={state.get('retrieved_docs', [])[:3]}\n"
            f"deterministic_plan={deterministic_plan}\n"
            "请返回 JSON：{\"plan\": [...]}"
        ),
        max_tokens=900,
    )


def _merge_llm_plan(
    deterministic_plan: list[dict[str, Any]],
    llm_plan: dict[str, Any] | None,
    required_tools: list[str],
) -> list[dict[str, Any]]:
    if not llm_plan or not isinstance(llm_plan.get("plan"), list):
        return deterministic_plan

    deterministic_by_tool = {
        step["tool_name"]: step
        for step in deterministic_plan
    }
    merged: list[dict[str, Any]] = []
    used_tools: set[str] = set()

    for raw_step in llm_plan["plan"]:
        if not isinstance(raw_step, dict):
            continue
        tool_name = raw_step.get("tool_name")
        if tool_name not in required_tools or tool_name in used_tools:
            continue
        base_step = deterministic_by_tool[tool_name]
        merged.append(_sanitize_llm_step(raw_step, base_step))
        used_tools.add(tool_name)

    for tool_name in required_tools:
        if tool_name not in used_tools and tool_name in deterministic_by_tool:
            merged.append(deterministic_by_tool[tool_name])

    return merged or deterministic_plan


def _sanitize_llm_step(
    llm_step: dict[str, Any],
    base_step: dict[str, Any],
) -> dict[str, Any]:
    tool_name = base_step["tool_name"]
    arguments = dict(base_step.get("arguments", {}))
    llm_arguments = llm_step.get("arguments")
    if isinstance(llm_arguments, dict):
        for key, value in llm_arguments.items():
            if key in _allowed_argument_keys(tool_name) and _is_simple_json_value(value):
                arguments[key] = value

    purpose = llm_step.get("purpose")
    if not isinstance(purpose, str) or not purpose.strip():
        purpose = base_step.get("purpose", "")

    return {
        "tool_name": tool_name,
        "arguments": arguments,
        "purpose": purpose.strip(),
    }


def _allowed_argument_keys(tool_name: str) -> set[str]:
    return {
        "query_data_volume": {"table_name", "start_date", "end_date"},
        "query_task_runs": {"date", "task_name", "table_name", "status"},
        "query_table_partitions": {"table_name", "date"},
        "query_null_rate": {"table_name", "field_name", "start_date", "end_date"},
        "query_lineage": {"table_name", "direction", "depth"},
    }.get(tool_name, set())


def _is_simple_json_value(value: Any) -> bool:
    return value is None or isinstance(value, str | int | float | bool)
