from __future__ import annotations

import re
from typing import Any

from app.workflow.llm_decisions import append_llm_decision, ask_deepseek_json
from app.workflow.state import DEMO_BIZ_DATE, DiagnosisState


DATE_PATTERN = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")
DAG_PATTERN = re.compile(r"\bDAG\s+([a-z][a-z0-9_]+)\b", re.IGNORECASE)
IDENTIFIER_PATTERN = re.compile(r"\b[a-z][a-z0-9_]*\b", re.IGNORECASE)
FIELD_PATTERN = re.compile(r"\b([a-z][a-z0-9_]*)\s*字段")
PERCENT_DROP_PATTERN = re.compile(r"下降\s*(\d+(?:\.\d+)?)\s*%")


def alert_parser_node(state: DiagnosisState) -> dict[str, Any]:
    raw_alert = state.get("raw_alert", "").strip()
    context: dict[str, Any] = {
        "raw_alert": raw_alert,
        "biz_date": _parse_date(raw_alert),
        "symptoms": _parse_symptoms(raw_alert),
    }

    task_name = _parse_task_name(raw_alert)
    if task_name:
        context["task_name"] = task_name

    table_name = _parse_table_name(raw_alert, task_name)
    if table_name:
        context["table_name"] = table_name

    field_name = _parse_field_name(raw_alert)
    if field_name:
        context["field_name"] = field_name

    change_ratio = _parse_change_ratio(raw_alert)
    if change_ratio is not None:
        context["change_ratio"] = change_ratio

    llm_context, llm_decision = _parse_with_deepseek(raw_alert)
    if llm_context:
        context = _merge_llm_context(context, llm_context)

    if not _has_minimum_context(context):
        return {
            "alert_context": context,
            "llm_decisions": append_llm_decision(state.get("llm_decisions"), llm_decision),
            "needs_clarification": True,
            "clarification_question": (
                "我需要补充几个信息才能诊断：具体是哪张表或哪个任务？"
                "异常表现是数据量下降、分区缺失、任务失败，还是字段质量异常？"
            ),
        }

    return {
        "alert_context": context,
        "llm_decisions": append_llm_decision(state.get("llm_decisions"), llm_decision),
        "needs_clarification": False,
        "clarification_question": "",
    }


def _parse_date(raw_alert: str) -> str:
    match = DATE_PATTERN.search(raw_alert)
    if match:
        return match.group(1)
    if "今天" in raw_alert or "今日" in raw_alert:
        return DEMO_BIZ_DATE
    return DEMO_BIZ_DATE


def _parse_task_name(raw_alert: str) -> str | None:
    dag_match = DAG_PATTERN.search(raw_alert)
    if dag_match:
        return dag_match.group(1)

    if not ("任务" in raw_alert or "运行失败" in raw_alert or "task" in raw_alert.casefold()):
        return None

    for identifier in IDENTIFIER_PATTERN.findall(raw_alert):
        lowered = identifier.lower()
        if lowered.endswith("_daily") or lowered.endswith("_job"):
            return lowered
    return None


def _parse_table_name(raw_alert: str, task_name: str | None) -> str | None:
    if task_name and DAG_PATTERN.search(raw_alert):
        if task_name.endswith("_daily"):
            return task_name[: -len("_daily")]
        if task_name.endswith("_job"):
            return task_name[: -len("_job")]

    identifiers = [identifier.lower() for identifier in IDENTIFIER_PATTERN.findall(raw_alert)]
    for identifier in identifiers:
        if identifier.startswith(("ods_", "dwd_", "dws_", "ads_")):
            return identifier

    if task_name:
        if task_name.endswith("_daily"):
            return task_name[: -len("_daily")]
        if task_name.endswith("_job"):
            return task_name[: -len("_job")]
    return None


def _parse_field_name(raw_alert: str) -> str | None:
    match = FIELD_PATTERN.search(raw_alert)
    if match:
        return match.group(1).lower()
    if "user_id" in raw_alert:
        return "user_id"
    return None


def _parse_change_ratio(raw_alert: str) -> float | None:
    match = PERCENT_DROP_PATTERN.search(raw_alert)
    if match:
        return round(-float(match.group(1)) / 100, 4)
    return None


def _parse_symptoms(raw_alert: str) -> list[str]:
    symptoms: list[str] = []
    lowered = raw_alert.casefold()
    if "dag" in lowered or "任务失败" in raw_alert or "运行失败" in raw_alert:
        symptoms.append("airflow_task_failed")
    if "分区" in raw_alert or "dt=" in lowered or "没有生成" in raw_alert:
        symptoms.append("partition_missing")
    if "数据量" in raw_alert or "行数" in raw_alert or "下降" in raw_alert:
        symptoms.append("data_volume_drop")
    if "空值率" in raw_alert or "null" in lowered:
        symptoms.append("null_rate_spike")
    return symptoms


def _has_minimum_context(context: dict[str, Any]) -> bool:
    has_target = bool(context.get("table_name") or context.get("task_name"))
    has_symptom = bool(context.get("symptoms"))
    return has_target and has_symptom


def _parse_with_deepseek(raw_alert: str) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    return ask_deepseek_json(
        node="AlertParser",
        system_prompt=(
            "你是 DataOps 告警解析器。只返回 JSON，不要解释。"
            "字段必须来自：table_name, task_name, field_name, biz_date, symptoms, change_ratio, needs_clarification。"
            "symptoms 只能包含 airflow_task_failed, partition_missing, data_volume_drop, null_rate_spike。"
            "无法确定的字段用 null 或空数组。"
        ),
        user_prompt=f"解析这个告警：{raw_alert}",
        max_tokens=500,
    )


def _merge_llm_context(
    deterministic_context: dict[str, Any],
    llm_context: dict[str, Any],
) -> dict[str, Any]:
    context = dict(deterministic_context)
    for key in ("table_name", "task_name", "field_name", "biz_date"):
        value = llm_context.get(key)
        if isinstance(value, str) and value.strip() and not context.get(key):
            context[key] = value.strip()

    symptoms = llm_context.get("symptoms")
    if isinstance(symptoms, list):
        allowed = {
            "airflow_task_failed",
            "partition_missing",
            "data_volume_drop",
            "null_rate_spike",
        }
        merged = [*context.get("symptoms", [])]
        for symptom in symptoms:
            if symptom in allowed and symptom not in merged:
                merged.append(symptom)
        context["symptoms"] = merged

    change_ratio = llm_context.get("change_ratio")
    if isinstance(change_ratio, int | float) and context.get("change_ratio") is None:
        context["change_ratio"] = round(float(change_ratio), 4)

    if llm_context.get("needs_clarification") is True:
        context["llm_needs_clarification"] = True
    return context
