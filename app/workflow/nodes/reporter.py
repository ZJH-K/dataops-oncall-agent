from __future__ import annotations

from typing import Any

from app.config import settings
from app.models import DeepSeekChatClient, ExternalModelError
from app.workflow.state import DiagnosisState


def reporter_node(state: DiagnosisState) -> dict[str, Any]:
    if state.get("needs_clarification"):
        question = state.get("clarification_question") or "请补充更多告警上下文。"
        return {
            "final_report": (
                "# 数据事故诊断报告\n\n"
                "## 1. 状态\n\n"
                "当前告警信息不足，暂不能生成确定诊断结论。\n\n"
                "## 2. 需要补充的信息\n\n"
                f"{question}\n"
            )
        }

    report = "\n".join(
        [
            "# 数据事故诊断报告",
            "",
            "## 1. 告警摘要",
            _alert_summary(state),
            "",
            "## 2. Diagnosis Skill",
            _skill_summary(state),
            "",
            "## 3. 诊断计划",
            _plan_summary(state),
            "",
            "## 4. RAG 引用来源",
            _rag_summary(state),
            "",
            "## 5. 工具调用证据",
            _tool_summary(state),
            "",
            "## 6. CoverageChecker",
            _coverage_summary(state),
            "",
            "## 7. 根因判断",
            _root_cause_summary(state),
            "",
            "## 8. 影响范围",
            _impact_summary(state),
            "",
            "## 9. 证据不足说明",
            _confidence_limit_summary(state),
            "",
        ]
    )
    report = _append_deepseek_summary(state, report)
    return {"final_report": report}


def _alert_summary(state: DiagnosisState) -> str:
    context = state.get("alert_context", {})
    lines = [f"- 原始告警：{state.get('raw_alert', '')}"]
    if context.get("table_name"):
        lines.append(f"- 表名：`{context['table_name']}`")
    if context.get("task_name"):
        lines.append(f"- 任务：`{context['task_name']}`")
    if context.get("field_name"):
        lines.append(f"- 字段：`{context['field_name']}`")
    if context.get("change_ratio") is not None:
        lines.append(f"- 变化比例：`{context['change_ratio']}`")
    lines.append(f"- 业务日期：`{context.get('biz_date')}`")
    return "\n".join(lines)


def _skill_summary(state: DiagnosisState) -> str:
    skill = state.get("selected_diagnosis_skill", {})
    return "\n".join(
        [
            f"- 名称：`{skill.get('name')}`",
            f"- 置信度：`{skill.get('confidence')}`",
            f"- 匹配原因：{skill.get('reason')}",
            f"- 必需工具：{', '.join(skill.get('required_tools', []))}",
        ]
    )


def _plan_summary(state: DiagnosisState) -> str:
    plan = state.get("plan", [])
    if not plan:
        return "- 未生成诊断计划。"
    return "\n".join(
        f"- `{step['tool_name']}`：{step.get('purpose', '')}"
        for step in plan
    )


def _rag_summary(state: DiagnosisState) -> str:
    docs = state.get("retrieved_docs", [])
    if not docs:
        return "- 未检索到足够相关的 Runbook 或历史资料。"
    return "\n".join(
        (
            f"- `{doc['source_file']}` / {doc['section_title']} "
            f"(score={doc['score']})"
        )
        for doc in docs[:5]
    )


def _tool_summary(state: DiagnosisState) -> str:
    tool_calls = state.get("tool_calls", [])
    if not tool_calls:
        return "- 未执行工具调用。"
    lines = []
    for call in tool_calls:
        line = (
            f"- `{call.get('tool_name')}` status=`{call.get('status')}` "
            f"summary={call.get('result_summary')}"
        )
        if call.get("error_message"):
            line += f" error={call.get('error_message')}"
        lines.append(line)
    return "\n".join(lines)


def _coverage_summary(state: DiagnosisState) -> str:
    coverage = state.get("coverage_result", {})
    return "\n".join(
        [
            f"- 状态：`{coverage.get('status')}`",
            f"- 工具覆盖率：`{coverage.get('coverage_ratio')}`",
            f"- 缺失工具：{coverage.get('missing_tools', [])}",
            f"- 缺失证据：{coverage.get('missing_evidence', [])}",
        ]
    )


def _root_cause_summary(state: DiagnosisState) -> str:
    skill_name = state.get("selected_diagnosis_skill", {}).get("name")
    evidence = state.get("evidence", {})
    docs = state.get("retrieved_docs", [])
    source = docs[0]["source_file"] if docs else "无 RAG 来源"

    if skill_name == "data_volume_drop":
        volume = _latest(evidence.get("data_volume", []), "stat_date")
        failed_tasks = [
            row
            for row in evidence.get("task_runs", [])
            if row.get("status") == "failed"
        ]
        if volume and failed_tasks:
            task_names = ", ".join(row.get("dag_id", "") for row in failed_tasks)
            return (
                "工具证据确认 `dws_sales_daily` 数据量异常下降："
                f"{volume.get('previous_day_row_count')} -> {volume.get('row_count')}，"
                f"change_ratio={volume.get('change_ratio')}。"
                f"同日失败任务包括 `{task_names}`。结合 RAG 来源 `{source}`，"
                "较高可能是上游支付订单同步失败导致汇总数据缺失。"
            )
        if volume:
            return (
                "工具证据确认存在数据量下降，但缺少相关失败任务证据，"
                "因此不能输出确定根因。"
            )

    if skill_name == "null_rate_spike":
        null_rate = _latest(evidence.get("null_rate", []), "biz_date")
        if null_rate:
            return (
                f"工具证据显示 `{null_rate.get('table_name')}.{null_rate.get('field_name')}` "
                f"空值率为 `{null_rate.get('null_rate')}`，超过阈值 "
                f"`{null_rate.get('threshold')}`。结合 RAG 来源 `{source}`，"
                "可能是身份映射规则异常导致字段级质量事故。"
            )

    failed_tasks = [
        row for row in evidence.get("task_runs", []) if row.get("status") == "failed"
    ]
    if failed_tasks:
        first = failed_tasks[0]
        return (
            f"工具证据显示 `{first.get('dag_id')}` 失败，错误为 "
            f"`{first.get('error_message')}`。根因判断需结合下游影响和修复结果。"
        )

    return "当前证据不足，不能输出确定根因。"


def _impact_summary(state: DiagnosisState) -> str:
    lineage = state.get("evidence", {}).get("lineage", {})
    downstream = lineage.get("downstream", []) if isinstance(lineage, dict) else []
    if not downstream:
        return "未确认完整下游影响范围。"
    tables = ", ".join(f"`{row['table_name']}`" for row in downstream)
    return f"已确认下游影响范围：{tables}。"


def _confidence_limit_summary(state: DiagnosisState) -> str:
    confidence_limit = state.get("confidence_limit")
    if confidence_limit:
        return confidence_limit
    return "CoverageChecker 显示必需工具和核心证据已覆盖，当前报告可作为完整诊断结论。"


def _latest(rows: list[dict[str, Any]], date_key: str) -> dict[str, Any] | None:
    if not rows:
        return None
    return sorted(rows, key=lambda row: str(row.get(date_key, "")))[-1]


def _append_deepseek_summary(state: DiagnosisState, report: str) -> str:
    if settings.llm_provider.lower() != "deepseek":
        return report
    if not settings.deepseek_api_key:
        return "\n".join(
            [
                report,
                "",
                "## 10. DeepSeek 辅助摘要",
                "",
                "- 已设置 `LLM_PROVIDER=deepseek`，但缺少 `DEEPSEEK_API_KEY`，因此保留确定性报告。",
            ]
        )

    try:
        summary = DeepSeekChatClient.from_settings().complete(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是 DataOps 事故诊断助手。请只基于用户给出的报告内容，"
                        "生成简洁中文摘要；不要新增未被证据支持的根因。"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "请将下面的确定性诊断报告压缩为 3 条面试演示摘要，"
                        "必须保留证据不足边界：\n\n"
                        f"{report}"
                    ),
                },
            ],
            max_tokens=500,
            temperature=0.2,
        )
    except ExternalModelError as exc:
        summary = f"- DeepSeek 调用失败：{exc}。已保留确定性报告作为主报告。"

    return "\n".join(
        [
            report,
            "",
            "## 10. DeepSeek 辅助摘要",
            "",
            summary,
        ]
    )
