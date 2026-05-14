from app.workflow.nodes import alert_parser, diagnosis_skill_matcher, planner


def test_deepseek_alert_parser_can_fill_missing_context(monkeypatch) -> None:
    def fake_ask_deepseek_json(*args, **kwargs):
        return (
            {
                "table_name": "dws_sales_daily",
                "biz_date": "2026-05-14",
                "symptoms": ["data_volume_drop"],
                "change_ratio": -0.92,
                "needs_clarification": False,
            },
            {"node": "AlertParser", "provider": "deepseek", "status": "success"},
        )

    monkeypatch.setattr(alert_parser, "ask_deepseek_json", fake_ask_deepseek_json)

    result = alert_parser.alert_parser_node(
        {"raw_alert": "今天销售报表数据量下降 92%", "llm_decisions": []}
    )

    assert result["needs_clarification"] is False
    assert result["alert_context"]["table_name"] == "dws_sales_daily"
    assert result["alert_context"]["symptoms"] == ["data_volume_drop"]
    assert result["llm_decisions"][0]["node"] == "AlertParser"


def test_deepseek_skill_matcher_can_select_valid_builtin_skill(monkeypatch) -> None:
    def fake_ask_deepseek_json(*args, **kwargs):
        return (
            {
                "skill_name": "data_volume_drop",
                "confidence": 0.93,
                "needs_clarification": False,
                "reason": "告警描述了数据量下降。",
            },
            {"node": "DiagnosisSkillMatcher", "provider": "deepseek", "status": "success"},
        )

    monkeypatch.setattr(
        diagnosis_skill_matcher,
        "ask_deepseek_json",
        fake_ask_deepseek_json,
    )

    result = diagnosis_skill_matcher.diagnosis_skill_matcher_node(
        {
            "raw_alert": "dws_sales_daily 今日数据量下降 92%",
            "alert_context": {"table_name": "dws_sales_daily"},
            "llm_decisions": [],
        }
    )

    assert result["needs_clarification"] is False
    assert result["selected_diagnosis_skill"]["name"] == "data_volume_drop"
    assert result["selected_diagnosis_skill"]["reason"].startswith("DeepSeek decision")
    assert result["llm_decisions"][0]["node"] == "DiagnosisSkillMatcher"


def test_deepseek_planner_can_reorder_plan_but_required_tools_remain(monkeypatch) -> None:
    def fake_ask_deepseek_json(*args, **kwargs):
        return (
            {
                "plan": [
                    {
                        "tool_name": "query_lineage",
                        "purpose": "先判断下游影响",
                        "arguments": {"table_name": "dws_sales_daily", "direction": "both"},
                    },
                    {
                        "tool_name": "query_data_volume",
                        "purpose": "确认数据量趋势",
                        "arguments": {"table_name": "dws_sales_daily"},
                    },
                    {"tool_name": "unknown_tool", "purpose": "无效工具", "arguments": {}},
                ]
            },
            {"node": "Planner", "provider": "deepseek", "status": "success"},
        )

    monkeypatch.setattr(planner, "ask_deepseek_json", fake_ask_deepseek_json)

    result = planner.planner_node(
        {
            "selected_diagnosis_skill": {
                "name": "data_volume_drop",
                "required_tools": ["query_data_volume", "query_lineage"],
            },
            "alert_context": {"table_name": "dws_sales_daily", "biz_date": "2026-05-14"},
            "retrieved_docs": [],
            "llm_decisions": [],
        }
    )

    assert [step["tool_name"] for step in result["plan"]] == [
        "query_lineage",
        "query_data_volume",
    ]
    assert result["plan"][0]["purpose"] == "先判断下游影响"
    assert result["llm_decisions"][0]["node"] == "Planner"
