from app.skills.loader import load_builtin_skills
from app.skills.matcher import DiagnosisSkillMatcher


def test_clear_demo_alerts_match_expected_skills() -> None:
    matcher = DiagnosisSkillMatcher(load_builtin_skills())

    cases = [
        (
            "DAG dwd_order_detail_daily 今天凌晨运行失败，请帮我诊断原因。",
            "airflow_task_failed",
        ),
        (
            "dws_sales_daily 今天没有生成 dt=2026-05-14 分区，请帮我排查。",
            "partition_missing",
        ),
        (
            "dws_sales_daily 今日数据量较昨日下降 92%，请判断是否存在数据事故。",
            "data_volume_drop",
        ),
        (
            "ads_user_profile 表中 user_id 字段空值率突然升高，请分析影响范围。",
            "null_rate_spike",
        ),
    ]

    for alert, expected_skill in cases:
        result = matcher.match(alert)

        assert result.skill_name == expected_skill
        assert not result.needs_clarification
        assert result.confidence >= 0.65
        assert result.matched_terms


def test_ambiguous_alert_needs_clarification() -> None:
    matcher = DiagnosisSkillMatcher(load_builtin_skills())

    result = matcher.match("今天的数据好像有点问题，帮我看一下。")

    assert result.skill_name is None
    assert result.needs_clarification
    assert result.confidence < 0.65

