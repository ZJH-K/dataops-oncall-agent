# 05 API Specification - DataOps OnCall Agent

版本：v0.1
日期：2026-05-14
关联文档：01-product-requirements.md、03-user-flow.md、04-technical-design.md

## 1. API 设计目标

本文档定义 DataOps OnCall Agent 的 HTTP API。API 主要服务于三个目标：

- 支持前端演示完整诊断流程。
- 支持后端模块开发和测试。
- 支持面试时讲清楚 Agent 应用的输入、状态、工具证据和报告输出。

MVP API 不追求企业级权限、多租户和复杂鉴权，优先保证接口清晰、数据结构稳定、错误可解释。

## 2. 基础约定

### 2.1 Base URL

```text
http://localhost:9900
```

### 2.2 Content-Type

普通请求：

```http
Content-Type: application/json
```

流式诊断：

```http
Content-Type: text/event-stream
```

### 2.3 时间格式

统一使用 ISO 8601 字符串：

```text
2026-05-14T09:30:00+08:00
```

日期字段使用：

```text
2026-05-14
```

### 2.4 通用响应结构

```json
{
  "code": 200,
  "message": "success",
  "data": {}
}
```

错误响应：

```json
{
  "code": 400,
  "message": "missing required field: alert",
  "error": {
    "type": "validation_error",
    "detail": "alert is required"
  }
}
```

### 2.5 通用错误码

| HTTP 状态码 | code | type | 说明 |
|-------------|------|------|------|
| 400 | 400 | validation_error | 请求参数错误 |
| 404 | 404 | not_found | 资源不存在 |
| 409 | 409 | state_conflict | 当前 session 状态不允许该操作 |
| 422 | 422 | diagnosis_clarification_required | 需要用户补充信息 |
| 500 | 500 | internal_error | 服务内部错误 |
| 503 | 503 | tool_unavailable | MCP Tool 或外部 provider 不可用 |

## 3. 数据模型概览

### 3.1 AlertContext

```json
{
  "table_name": "dws_sales_daily",
  "task_name": null,
  "field_name": null,
  "date": "2026-05-14",
  "time_range": "today_vs_yesterday",
  "symptoms": ["data_volume_drop"],
  "change_ratio": -0.92
}
```

### 3.2 DiagnosisSkillSummary

```json
{
  "name": "data_volume_drop",
  "display_name": "Data Volume Drop",
  "summary": "Detect and diagnose abnormal table row count drops.",
  "confidence": 0.91,
  "reason": "用户明确描述今日数据量较昨日下降 92%，符合数据量突降场景。",
  "required_tools": [
    "query_data_volume",
    "query_task_runs",
    "query_table_partitions",
    "query_lineage"
  ],
  "evidence_requirements": [
    "recent_row_count_trend",
    "current_partition_status",
    "related_task_status",
    "downstream_impact"
  ]
}
```

### 3.3 RetrievedDocument

```json
{
  "source_file": "runbooks/data_volume_drop.md",
  "doc_type": "runbook",
  "section_title": "数据量突降排查步骤",
  "chunk_id": "runbook-data-volume-drop-001",
  "score": 0.88,
  "content_summary": "先确认表分区是否产出，再检查上游任务和最近 7 天行数趋势。"
}
```

### 3.4 ToolCall

```json
{
  "tool_call_id": "toolcall-001",
  "tool_name": "query_data_volume",
  "arguments": {
    "table_name": "dws_sales_daily",
    "start_date": "2026-05-08",
    "end_date": "2026-05-14"
  },
  "status": "success",
  "result_summary": "2026-05-14 row_count=800, previous_day=10000, drop_ratio=92%",
  "latency_ms": 42,
  "created_at": "2026-05-14T09:30:00+08:00"
}
```

### 3.5 CoverageResult

```json
{
  "required_tools_coverage": 1.0,
  "missing_tools": [],
  "evidence_coverage": 1.0,
  "missing_evidence": [],
  "can_generate_final_report": true,
  "confidence_limit": "high"
}
```

## 4. Diagnose API

### 4.1 POST /api/diagnose

发起一次非流式诊断。适合测试和后端调试。前端演示优先使用流式接口。

#### Request

```http
POST /api/diagnose
Content-Type: application/json
```

```json
{
  "session_id": "session-001",
  "alert": "dws_sales_daily 今日数据量较昨日下降 92%，请判断是否存在数据事故。",
  "options": {
    "stream": false,
    "save_incident": true,
    "debug": true
  }
}
```

#### 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| session_id | string | 是 | 会话 ID，用于多轮状态 |
| alert | string | 是 | 用户输入的告警文本 |
| options.stream | boolean | 否 | 是否流式，非流式接口默认 false |
| options.save_incident | boolean | 否 | 是否保存事故记录，默认 true |
| options.debug | boolean | 否 | 是否返回中间状态，默认 false |

#### Response

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "session_id": "session-001",
    "incident_id": "incident-20260514-001",
    "status": "completed",
    "alert_context": {
      "table_name": "dws_sales_daily",
      "date": "2026-05-14",
      "symptoms": ["data_volume_drop"],
      "change_ratio": -0.92
    },
    "selected_diagnosis_skill": {
      "name": "data_volume_drop",
      "confidence": 0.91,
      "reason": "用户描述了明确的数据量突降。"
    },
    "retrieved_docs": [],
    "plan": [
      "查询最近 7 天数据量趋势",
      "查询当前表分区状态",
      "查询相关任务状态",
      "查询下游影响范围"
    ],
    "tool_calls": [],
    "coverage_result": {
      "required_tools_coverage": 1.0,
      "evidence_coverage": 1.0,
      "confidence_limit": "high"
    },
    "final_report": "# 数据事故诊断报告\n..."
  }
}
```

#### Clarification Response

当告警信息不足或 Skill 置信度过低时：

```json
{
  "code": 422,
  "message": "clarification required",
  "data": {
    "session_id": "session-001",
    "status": "needs_clarification",
    "clarification_question": "请补充具体表名、指标名或异常类型。",
    "candidate_diagnosis_skills": [
      {
        "name": "partition_missing",
        "score": 0.46,
        "reason": "用户提到报表异常，可能是分区缺失。"
      },
      {
        "name": "data_volume_drop",
        "score": 0.43,
        "reason": "用户提到数据不对，可能是数据量异常。"
      }
    ]
  }
}
```

### 4.2 POST /api/diagnose/stream

发起一次流式诊断。用于前端展示 Agent 过程。

#### Request

```http
POST /api/diagnose/stream
Content-Type: application/json
Accept: text/event-stream
```

```json
{
  "session_id": "session-001",
  "alert": "dws_sales_daily 今日数据量较昨日下降 92%，请判断是否存在数据事故。"
}
```

#### SSE Event 类型

| event type | 说明 |
|------------|------|
| status | 当前阶段状态 |
| alert_context | 告警解析结果 |
| skill_matched | Skill 匹配结果 |
| clarification_required | 需要用户补充信息 |
| docs_retrieved | RAG 检索结果 |
| plan_created | 诊断计划 |
| tool_call_started | 工具调用开始 |
| tool_call_completed | 工具调用完成 |
| tool_call_failed | 工具调用失败 |
| coverage_checked | 覆盖率检查结果 |
| report_delta | 报告流式片段 |
| completed | 诊断完成 |
| error | 错误 |

#### Event 示例

```text
event: skill_matched
data: {"name":"data_volume_drop","confidence":0.91,"reason":"用户明确描述数据量下降 92%。"}
```

```text
event: tool_call_completed
data: {"tool_name":"query_data_volume","status":"success","result_summary":"今日行数 800，昨日行数 10000，下降 92%。"}
```

```text
event: completed
data: {"incident_id":"incident-20260514-001","status":"completed"}
```

## 5. Chat API

### 5.1 POST /api/chat

用于诊断后的多轮追问。系统需要读取 Session State，而不是只依赖聊天历史。

#### Request

```http
POST /api/chat
Content-Type: application/json
```

```json
{
  "session_id": "session-001",
  "message": "它影响哪些下游报表？"
}
```

#### Response

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "session_id": "session-001",
    "incident_id": "incident-20260514-001",
    "answer": "根据当前 incident 的 query_lineage 工具结果，dws_sales_daily 影响 ads_sales_report 和 ads_revenue_dashboard。",
    "used_state": {
      "current_table": "dws_sales_daily",
      "selected_diagnosis_skill": "data_volume_drop"
    },
    "references": [
      {
        "type": "tool_call",
        "tool_name": "query_lineage",
        "tool_call_id": "toolcall-004"
      }
    ]
  }
}
```

## 6. Skills API

### 6.1 GET /api/skills

查询所有内置 Diagnosis Skill。

#### Response

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "skills": [
      {
        "name": "airflow_task_failed",
        "display_name": "Airflow Task Failed",
        "summary": "Diagnose failed scheduled data tasks.",
        "triggers": ["任务失败", "DAG 失败", "Airflow failed"],
        "required_tools": ["query_task_runs", "query_lineage"],
        "risk_level": "medium"
      }
    ]
  }
}
```

### 6.2 GET /api/skills/{skill_name}

查询某个 Diagnosis Skill 的完整定义。

#### Response

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "name": "data_volume_drop",
    "display_name": "Data Volume Drop",
    "summary": "Detect and diagnose abnormal table row count drops.",
    "triggers": ["数据量下降", "行数变少", "环比下降"],
    "required_tools": [
      "query_data_volume",
      "query_task_runs",
      "query_table_partitions",
      "query_lineage"
    ],
    "evidence_requirements": [
      "recent_row_count_trend",
      "current_partition_status",
      "related_task_status",
      "downstream_impact"
    ],
    "risk_level": "medium",
    "requires_confirmation": false,
    "runbook_preview": "# 数据量突降排查 Runbook\n..."
  }
}
```

### 6.3 POST /api/skills/match

调试 Skill 匹配逻辑。用于测试和面试演示。

#### Request

```json
{
  "alert": "dws_sales_daily 今日数据量较昨日下降 92%。",
  "debug": true
}
```

#### Response

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "selected_diagnosis_skill": {
      "name": "data_volume_drop",
      "confidence": 0.91,
      "reason": "命中触发词：数据量、下降；并提取到下降比例。"
    },
    "candidate_diagnosis_skills": [
      {
        "name": "data_volume_drop",
        "score": 0.91
      },
      {
        "name": "partition_missing",
        "score": 0.38
      }
    ]
  }
}
```

## 7. Incidents API

### 7.1 GET /api/incidents

分页查询事故记录。

#### Request

```http
GET /api/incidents?page=1&page_size=20&skill_name=data_volume_drop
```

#### Response

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "items": [
      {
        "incident_id": "incident-20260514-001",
        "title": "dws_sales_daily 数据量突降",
        "status": "completed",
        "severity": "P2",
        "selected_diagnosis_skill": "data_volume_drop",
        "created_at": "2026-05-14T09:30:00+08:00"
      }
    ],
    "page": 1,
    "page_size": 20,
    "total": 1
  }
}
```

### 7.2 GET /api/incidents/{incident_id}

查询事故详情。

#### Response

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "incident_id": "incident-20260514-001",
    "session_id": "session-001",
    "title": "dws_sales_daily 数据量突降",
    "raw_alert": "dws_sales_daily 今日数据量较昨日下降 92%。",
    "status": "completed",
    "severity": "P2",
    "alert_context": {},
    "selected_diagnosis_skill": "data_volume_drop",
    "coverage_result": {},
    "final_report": "# 数据事故诊断报告\n...",
    "created_at": "2026-05-14T09:30:00+08:00"
  }
}
```

### 7.3 GET /api/incidents/{incident_id}/tool-calls

查询某次事故的工具调用记录。

#### Response

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "incident_id": "incident-20260514-001",
    "tool_calls": [
      {
        "tool_call_id": "toolcall-001",
        "tool_name": "query_data_volume",
        "status": "success",
        "arguments": {
          "table_name": "dws_sales_daily"
        },
        "result_summary": "今日行数 800，昨日行数 10000。",
        "latency_ms": 42
      }
    ]
  }
}
```

## 8. Tools Debug API

这些接口只用于开发调试和面试演示，不一定暴露给真实用户。

### 8.1 GET /api/tools

查询可用 MCP Tool。

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "tools": [
      {
        "name": "query_data_volume",
        "description": "Query table row count trend by date range.",
        "input_schema": {
          "table_name": "string",
          "start_date": "date",
          "end_date": "date"
        }
      }
    ]
  }
}
```

### 8.2 POST /api/tools/{tool_name}/invoke

直接调用工具，用于调试。

#### Request

```json
{
  "arguments": {
    "table_name": "dws_sales_daily",
    "start_date": "2026-05-08",
    "end_date": "2026-05-14"
  }
}
```

#### Response

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "tool_name": "query_data_volume",
    "status": "success",
    "result": {
      "table_name": "dws_sales_daily",
      "rows": [
        {"date": "2026-05-13", "row_count": 10000},
        {"date": "2026-05-14", "row_count": 800}
      ]
    }
  }
}
```

## 9. RAG Debug API

### 9.1 POST /api/rag/search

调试 RAG 检索结果。

#### Request

```json
{
  "query": "dws_sales_daily 数据量下降",
  "filters": {
    "skill_name": "data_volume_drop",
    "table_name": "dws_sales_daily"
  },
  "top_k": 5
}
```

#### Response

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "results": [
      {
        "source_file": "runbooks/data_volume_drop.md",
        "doc_type": "runbook",
        "section_title": "数据量突降排查步骤",
        "chunk_id": "runbook-data-volume-drop-001",
        "score": 0.88,
        "content_summary": "先确认表分区是否产出，再检查上游任务和最近 7 天行数趋势。"
      }
    ]
  }
}
```

## 10. Eval API 可选

MVP 可以先用命令行 eval，不一定做 API。如果做接口，可用于前端展示项目质量指标。

### 10.1 POST /api/eval/run

```json
{
  "dataset": "skill_match_cases",
  "limit": 20
}
```

Response：

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "dataset": "skill_match_cases",
    "total": 20,
    "accuracy": 0.9,
    "failed_cases": []
  }
}
```

## 11. Health API

### 11.1 GET /api/health

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "status": "ok",
    "version": "0.1.0",
    "database": "ok",
    "mcp_server": "ok",
    "rag_index": "ok",
    "skills_loaded": 4
  }
}
```

## 12. 前端演示接口使用顺序

推荐前端流程：

```text
1. GET /api/health
2. GET /api/skills
3. POST /api/diagnose/stream
4. GET /api/incidents/{incident_id}/tool-calls
5. POST /api/chat
6. GET /api/incidents/{incident_id}
```

## 13. API 设计取舍

| 设计 | 原因 |
|------|------|
| 同时提供非流式和流式诊断 | 非流式便于测试，流式便于演示 Agent 过程 |
| 提供 debug tools API | 方便面试展示工具层不是假的 |
| Skill 匹配单独提供接口 | 方便测试路由准确率 |
| Report 通过 incidents 查询 | 让诊断结果形成业务闭环 |
| Chat API 使用 session_id | 支持多轮追问和结构化状态 |

## 14. 面试讲解口径

可以这样解释 API 设计：

```text
我把 API 分成诊断、Skill、工具调试、RAG 调试和事故记录几组。诊断接口负责端到端流程，Skill 和工具接口便于调试中间结果，事故接口用于保存最终报告。这样面试时不仅能展示最终答案，还能展示 Agent 是如何匹配 Skill、检索知识、调用工具和检查证据覆盖率的。
```
