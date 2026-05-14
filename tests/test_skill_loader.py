from app.skills.loader import load_builtin_skills


def test_loads_four_builtin_skills() -> None:
    skills = load_builtin_skills()

    assert set(skills) == {
        "airflow_task_failed",
        "partition_missing",
        "data_volume_drop",
        "null_rate_spike",
    }


def test_builtin_skills_have_required_strategy_fields() -> None:
    skills = load_builtin_skills()

    for skill in skills.values():
        assert skill.name
        assert skill.triggers
        assert skill.required_tools
        assert skill.evidence_requirements
        assert skill.runbook_text.strip()
        assert skill.examples_data


def test_data_volume_drop_skill_loads_expected_tools_and_example() -> None:
    skill = load_builtin_skills()["data_volume_drop"]

    assert skill.required_tools == [
        "query_data_volume",
        "query_task_runs",
        "query_table_partitions",
        "query_lineage",
    ]
    assert skill.examples_data[0].expected_skill == "data_volume_drop"
    assert skill.examples_data[0].expected_entities["table_name"] == "dws_sales_daily"

