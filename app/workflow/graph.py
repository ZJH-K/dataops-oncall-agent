from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from app.rag.indexer import DEFAULT_INDEX_PATH
from app.workflow.nodes.alert_parser import alert_parser_node
from app.workflow.nodes.coverage_checker import coverage_checker_node
from app.workflow.nodes.diagnosis_skill_matcher import diagnosis_skill_matcher_node
from app.workflow.nodes.incident_recorder import incident_recorder_node
from app.workflow.nodes.knowledge_retriever import knowledge_retriever_node
from app.workflow.nodes.planner import planner_node
from app.workflow.nodes.reporter import reporter_node
from app.workflow.nodes.tool_executor import tool_executor_node
from app.workflow.state import DiagnosisState


def build_diagnosis_graph(
    database_url: str | None = None,
    index_path: Path = DEFAULT_INDEX_PATH,
):
    graph = StateGraph(DiagnosisState)
    graph.add_node("AlertParser", alert_parser_node)
    graph.add_node("DiagnosisSkillMatcher", diagnosis_skill_matcher_node)
    graph.add_node(
        "KnowledgeRetriever",
        lambda state: knowledge_retriever_node(state, index_path=index_path),
    )
    graph.add_node("Planner", planner_node)
    graph.add_node(
        "ToolExecutor",
        lambda state: tool_executor_node(state, database_url=database_url),
    )
    graph.add_node("CoverageChecker", coverage_checker_node)
    graph.add_node("Reporter", reporter_node)
    graph.add_node(
        "IncidentRecorder",
        lambda state: incident_recorder_node(state, database_url=database_url),
    )

    graph.add_edge(START, "AlertParser")
    graph.add_conditional_edges(
        "AlertParser",
        _route_after_alert_parser,
        {
            "clarify": "Reporter",
            "match_skill": "DiagnosisSkillMatcher",
        },
    )
    graph.add_conditional_edges(
        "DiagnosisSkillMatcher",
        _route_after_skill_matcher,
        {
            "clarify": "Reporter",
            "retrieve": "KnowledgeRetriever",
        },
    )
    graph.add_edge("KnowledgeRetriever", "Planner")
    graph.add_edge("Planner", "ToolExecutor")
    graph.add_edge("ToolExecutor", "CoverageChecker")
    graph.add_conditional_edges(
        "CoverageChecker",
        _route_after_coverage_checker,
        {
            "retry_tools": "ToolExecutor",
            "report": "Reporter",
        },
    )
    graph.add_edge("Reporter", "IncidentRecorder")
    graph.add_edge("IncidentRecorder", END)
    return graph.compile()


def run_diagnosis(
    raw_alert: str,
    session_id: str | None = None,
    database_url: str | None = None,
    index_path: Path = DEFAULT_INDEX_PATH,
) -> DiagnosisState:
    compiled = build_diagnosis_graph(database_url=database_url, index_path=index_path)
    initial_state: DiagnosisState = {
        "session_id": session_id or f"session_{uuid4().hex[:12]}",
        "raw_alert": raw_alert,
        "tool_calls": [],
        "llm_decisions": [],
        "errors": [],
        "coverage_retry_count": 0,
    }
    return compiled.invoke(initial_state)


def _route_after_alert_parser(state: DiagnosisState) -> str:
    return "clarify" if state.get("needs_clarification") else "match_skill"


def _route_after_skill_matcher(state: DiagnosisState) -> str:
    return "clarify" if state.get("needs_clarification") else "retrieve"


def _route_after_coverage_checker(state: DiagnosisState) -> str:
    coverage = state.get("coverage_result", {})
    return "retry_tools" if coverage.get("action") == "retry_tools" else "report"
