# 08 Deployment - DataOps OnCall Agent

版本：v0.1
日期：2026-05-14
关联文档：04-technical-design.md、05-api-spec.md、06-database-schema.md

## 1. 部署目标

本项目的部署目标是保证本地演示稳定可复现。优先支持 Windows 本地开发环境，后续再补 Docker Compose。

部署需要满足：

- 一键初始化 SQLite 模拟数据。
- 一键构建 RAG index。
- 能检查本地 MCP Tool CLI，并启动 FastAPI 服务。
- 能打开 Demo UI 完成 4 个 MVP 场景演示。
- 能在面试前快速 reset 到稳定演示状态。

## 2. 推荐本地环境

| 项目 | 建议版本 |
|------|----------|
| Python | 3.11+ |
| uv | 最新稳定版 |
| OS | Windows 10/11 |
| Shell | PowerShell 7 或 CMD |
| Browser | Chrome / Edge |
| Database | SQLite |
| Vector Store | Chroma / FAISS / SQLite FTS，MVP 任选轻量方案 |

不建议 MVP 阶段依赖：

- Docker Desktop 必须可用。
- Milvus 必须启动。
- 真实 Airflow 服务。
- 真实 Spark/Flink 集群。

原因：这些重组件容易抢走项目重点，也会增加面试演示失败风险。

## 3. 项目目录

建议项目最终放在：

```text
E:\CrazyJobHunting\项目\dataops-oncall-agent
```

文档目录保持在：

```text
E:\CrazyJobHunting\项目
```

推荐结构：

```text
dataops-oncall-agent/
├── app/
├── mcp_servers/
├── docs/
├── scripts/
├── eval/
├── tests/
├── static/
├── data/
│   ├── dataops_oncall.db
│   └── rag_index.json
├── .env.example
├── pyproject.toml
└── README.md
```

## 4. 环境变量

`.env.example`：

```env
APP_ENV=local
APP_HOST=0.0.0.0
APP_PORT=9900
DATABASE_URL=sqlite:///data/dataops_oncall.db
LOG_LEVEL=INFO
```

注意：

- `.env` 不提交到仓库。
- `.env.example` 可以提交。
- 当前 MVP 不依赖 LLM Key，Skill 匹配和报告生成都可以本地运行。

## 5. 首次安装

### 5.1 安装 uv

如果本机已有 uv，可以跳过。

```bash
pip install uv
```

### 5.2 创建虚拟环境并安装依赖

```bash
cd E:\CrazyJobHunting\项目\dataops-oncall-agent
uv venv
.venv\Scripts\activate
uv sync
```

如果使用 pip：

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```

## 6. 初始化演示数据

### 6.1 重建数据库

```bash
uv run python scripts/reset_demo_data.py
```

这个脚本会执行：

- 删除旧的 `data/dataops_oncall.db`。
- 重新创建 SQLite schema。
- 清空旧的 incident 和 tool logs。

### 6.2 写入 seed 数据

```bash
uv run python scripts/seed_demo_data.py
```

seed 后应包含：

- 4 个 MVP demo scenarios。
- 5 张核心数据表元数据。
- 最近 7 天分区和数据量。
- 至少 1 个失败任务。
- 至少 1 个缺失分区。
- 至少 1 个数据量突降。
- 至少 1 个字段空值率异常。
- 血缘链路：`ods_orders -> dwd_order_detail -> dws_sales_daily -> ads_sales_report`。

### 6.3 构建 RAG index

```bash
uv run python scripts/build_rag_index.py
```

输入目录：

```text
docs/runbooks
docs/tables
docs/postmortems
docs/quality_rules
```

输出文件：

```text
data/rag_index.json
```

## 7. 启动服务

### 7.1 检查本地 MCP Tool CLI

当前 MVP 的 MCP Tool 入口是本地 JSON CLI，FastAPI 诊断流程会直接调用 provider 层。

```bash
uv run python mcp_servers/dataops_server.py
```

预期输出：

```text
{"tools":[...]}
```

### 7.2 启动 FastAPI

终端：

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 9900 --reload
```

访问：

```text
http://localhost:9900/docs
http://localhost:9900
```

### 7.3 健康检查

```bash
curl http://localhost:9900/api/health
```

预期：

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "status": "ok",
    "database": "ok",
    "mcp_server": "ok",
    "rag_index": "ok",
    "skills_loaded": 4
  }
}
```

## 8. 面试演示前重置流程

面试前运行：

```bash
uv run python scripts/reset_demo_data.py
uv run python scripts/seed_demo_data.py
uv run python scripts/build_rag_index.py
```

然后启动：

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 9900
```

建议演示前固定检查：

```bash
curl http://localhost:9900/api/health
curl http://localhost:9900/api/skills
```

## 9. 演示案例

### 9.1 数据量突降

```text
dws_sales_daily 今日数据量较昨日下降 92%，请判断是否存在数据事故。
```

预期展示：

- 匹配 `data_volume_drop`。
- 调用 `query_data_volume`、`query_task_runs`、`query_table_partitions`、`query_lineage`。
- CoverageChecker 显示工具和证据覆盖率。
- 报告包含下降比例和下游影响。

### 9.2 分区缺失

```text
dws_sales_daily 今天没有生成 dt=2026-05-14 分区，请帮我排查。
```

预期展示：

- 匹配 `partition_missing`。
- 查询当前表和上游表分区。
- 判断当前任务或上游依赖问题。

### 9.3 低置信度澄清

```text
今天销售报表不太对，帮我看看。
```

预期展示：

- 不直接生成报告。
- 返回候选 Diagnosis Skill。
- 请求用户补充表名或异常类型。

## 10. 本地调试命令

### 10.1 测试 Skill 匹配

```bash
curl -X POST http://localhost:9900/api/skills/match ^
  -H "Content-Type: application/json" ^
  -d "{\"alert\":\"dws_sales_daily 今日数据量较昨日下降 92%\",\"debug\":true}"
```

### 10.2 调试 MCP Tool CLI

```bash
uv run python mcp_servers/dataops_server.py --tool query_data_volume --args "{\"table_name\":\"dws_sales_daily\",\"start_date\":\"2026-05-08\",\"end_date\":\"2026-05-14\"}"
```

### 10.3 调试 RAG 检索

```bash
uv run pytest tests/test_rag_retriever.py -q
```

## 11. 测试运行

```bash
uv run pytest tests -q
```

只跑核心 smoke test：

```bash
uv run pytest tests/test_workflow_smoke.py -q
```

运行 eval：

```bash
uv run python eval/run_eval.py --dataset skill_match_cases
uv run python eval/run_eval.py --dataset rag_cases
uv run python eval/run_eval.py --dataset tool_coverage_cases
```

## 12. 可选 Docker Compose

MVP 阶段可以不做 Docker。如果要补，建议只包含 FastAPI 服务，不把 SQLite 和 RAG index 做复杂服务化。

示例：

```yaml
services:
  dataops-agent:
    build: .
    ports:
      - "9900:9900"
    env_file:
      - .env
    volumes:
      - ./data:/app/data
      - ./docs:/app/docs
    command: uvicorn app.main:app --host 0.0.0.0 --port 9900
```

如果后续把 MCP Tool 做成独立远程服务，可以拆成第二个 service。

## 13. 常见问题

### 13.1 uv 默认缓存目录异常

现象：Windows 环境中 `uv run` 报缓存目录或解释器权限问题。

处理：

```bash
uv --cache-dir .uv-cache run pytest tests -q
uv --cache-dir .uv-cache run uvicorn app.main:app --host 0.0.0.0 --port 9900
```

### 13.2 MCP Tool CLI 检查失败

现象：工具 CLI 无法列出或调用工具。

处理：

```bash
uv run python mcp_servers/dataops_server.py
```

### 13.3 RAG index 不存在

现象：RAG 检索为空或报错。

处理：

```bash
uv run python scripts/build_rag_index.py
```

### 13.4 dataops_oncall.db 数据不对

处理：

```bash
uv run python scripts/reset_demo_data.py
uv run python scripts/seed_demo_data.py
```

### 13.5 端口被占用

处理：

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 9901
```

## 14. 面试部署口径

可以这样说：

```text
这个项目的部署策略优先保证本地可复现演示。SQLite 负责模拟数据平台元数据，seed 脚本负责生成固定故障场景，本地 MCP Tool CLI 和 provider 层负责暴露工具能力，FastAPI 提供诊断接口和前端页面。真实环境下不需要改 Agent 主流程，只要把 SQLite provider 替换成 Airflow、Hive Metastore、DataHub 或数据质量平台 provider。
```

不要说：

```text
我已经接入真实生产 Airflow 和数仓。
```

应该说：

```text
当前是模拟数据平台，重点验证 Agent 诊断链路。工具层做了 provider 抽象，方便迁移真实系统。
```
