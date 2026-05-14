from app.workflow.nodes.coverage_checker import coverage_checker_node


def test_coverage_checker_requests_missing_tool_retry() -> None:
    state = {
        "selected_diagnosis_skill": {
            "required_tools": [
                "query_data_volume",
                "query_task_runs",
                "query_table_partitions",
                "query_lineage",
            ],
            "evidence_requirements": [
                "recent_row_count_trend",
                "current_partition_status",
                "related_task_status",
                "downstream_impact",
            ],
        },
        "tool_calls": [
            {"tool_name": "query_data_volume", "status": "success"},
            {"tool_name": "query_task_runs", "status": "success"},
            {"tool_name": "query_table_partitions", "status": "success"},
        ],
        "evidence": {
            "data_volume": [{"row_count": 800}],
            "task_runs": [{"status": "failed"}],
            "table_partitions": [{"status": "missing"}],
        },
        "coverage_retry_count": 0,
    }

    result = coverage_checker_node(state)

    assert result["pending_tools"] == ["query_lineage"]
    assert result["coverage_result"]["action"] == "retry_tools"
    assert result["coverage_result"]["coverage_ratio"] == 0.75
    assert "downstream_impact" in result["coverage_result"]["missing_evidence"]


def test_coverage_checker_limits_report_when_evidence_still_missing() -> None:
    state = {
        "selected_diagnosis_skill": {
            "required_tools": ["query_data_volume", "query_lineage"],
            "evidence_requirements": [
                "recent_row_count_trend",
                "downstream_impact",
            ],
        },
        "tool_calls": [
            {"tool_name": "query_data_volume", "status": "success"},
            {"tool_name": "query_lineage", "status": "success"},
        ],
        "evidence": {
            "data_volume": [{"row_count": 800}],
            "lineage": {"downstream": [], "upstream": []},
        },
        "coverage_retry_count": 1,
    }

    result = coverage_checker_node(state)

    assert result["coverage_result"]["action"] == "report"
    assert result["coverage_result"]["status"] == "partial"
    assert result["coverage_result"]["can_report"] is True
    assert result["coverage_result"]["missing_evidence"] == ["downstream_impact"]
    assert "不能过度确定根因" in result["confidence_limit"]
