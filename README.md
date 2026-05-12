# 律师智能体 Law Agent

面向律师执业流的云端法律 AI 工作流服务。项目目标不是做一个通用聊天机器人，而是把律师工作中的判断、检索、文书、风险提示、客户画像记忆和人工审阅组织成可追踪、可审计、可 7x24 在线运行的后端系统。

## 当前定位

这个项目目前已经具备一套轻量编排骨架：

- 识别用户意图：法规速查、类案检索、文书初稿、合同审查、通用问题。
- 按意图路由到不同处理流程。
- 调用工具层完成法规、案例、引用、文书等任务。
- 对输出做风险分级。
- 写入审计日志，保留 trace_id、意图、风险、工具调用等记录。
- 导入每周更新的律师客户画像 JSON，作为后续编排和策略判断的驱动数据源。

需要注意：LLM 客户端和真实 RAG 数据源目前仍是预留/配置型能力。没有外部 RAG API 时，法规、案例、引用核验、合同条款检索会返回空结果或降级结果；文书模板生成和客户画像建库不依赖外部服务。当前 LLM 调用入口切换为 MiniMax，云端正式版仍需接入知识库、OSS、RDS PostgreSQL 等服务。

## 云端部署定位

本项目计划部署为全天在线的云端法律 AI 后端服务，而不是只在本地运行的脚本或实验项目。

推荐分阶段落地：

1. **MVP 云端上线**：ECS + Docker Compose + Nginx + HTTPS。
2. **低运维部署**：后续可迁移到 SAE 镜像部署。
3. **企业级扩展**：当出现多服务、多副本、灰度发布需求后，再考虑 ACK / Kubernetes。

推荐云端组件：

- **FastAPI Law Agent**：主服务，负责业务 API、编排、风控、审计。
- **MiniMax**：当前 LLM 调用入口，使用 OpenAI 兼容模式接入。
- **阿里云知识库或 DashVector**：法律专业知识库检索。
- **RDS PostgreSQL**：业务数据、客户画像、审计日志、审阅任务。
- **OSS**：法规、案例、合同模板、上传文件、知识库源文件归档。
- **Redis / Tair（可选）**：短期会话缓存、任务状态缓存。
- **日志、监控、告警**：保证 7x24 服务可观测。

## 知识库与记忆系统设计

项目中的“知识库”和“记忆库”需要严格分层，不能混用。

### 法律专业知识库

用途：存放可随时更新的法律专业知识，包括法规、司法解释、案例、合同模板、内部研究资料。

推荐方案：

- MVP 阶段优先接入 **阿里云百炼知识库**，降低自建 RAG 成本。
- 如果后续需要更强的自定义检索、过滤、版本控制和多库路由，再接入 **DashVector** 自建向量检索层。
- 法律知识库只保存客观法律依据和专业资料，不保存律师个人策略偏好。

每条知识建议保留元数据：

```text
source_type: law / regulation / case / template / internal_note
jurisdiction: 全国 / 广东 / 深圳 / ...
authority_level: 法律 / 行政法规 / 司法解释 / 地方规定 / 案例 / 内部资料
effective_date
expire_date
source_url
version
uploaded_by
review_status
```

知识库更新流水线：

```text
法律文件 / 法规 / 案例 / 内部模板
└── 上传到 OSS
    └── 触发导入任务
        ├── 文档清洗
        ├── 分块
        ├── 元数据标注
        ├── 写入百炼知识库或 DashVector
        ├── 生成知识库版本号
        └── 写入审计日志
```

### 记忆系统

记忆分三层：

```text
Session Memory
└── 当前会话上下文，短期有效

Profile Memory
└── 律师画像、客户画像、办案策略、风险沟通偏好

Knowledge Memory
└── 法律知识、法规、案例、模板、内部研究资料
```

推荐处理方式：

- **Session Memory**：先存 RDS PostgreSQL 的 `sessions/messages` 表；并发上来后可加 Redis / Tair。
- **Profile Memory**：律师画像和客户画像保留结构化字段，云端正式版迁移到 RDS PostgreSQL。
- **Knowledge Memory**：法律知识进入阿里云知识库或 DashVector，通过 RAG 检索使用。

关键边界：

- 法律知识库用于回答“法律依据是什么”。
- 律师画像用于回答“这个案件应如何沟通、如何处理、是否适合推进”。
- 画像不能混入法律知识库当作法律依据，否则会把经验策略误包装成客观法律结论。

## 云端目标架构

```text
用户 / 律师 / 助理
└── Web / 飞书 / API
    └── Law Agent FastAPI 服务
        ├── LawOrchestrator
        ├── RiskLabeler
        ├── AuditLogger
        ├── ClientProfileStore
        ├── MiniMax LLM
        ├── 法律知识库：百炼知识库 / DashVector
        ├── 业务数据库：RDS PostgreSQL
        ├── 文件归档：OSS
        └── 监控 / 日志 / 告警
```

## 核心能力

### 法规速查

入口：`IntentType.REGULATION_QUERY`

流程：

1. 识别法规查询意图。
2. 调用 `ResearchAgent.search_regulations`。
3. 通过 `RAGClient` 请求外部法规库。
4. 尝试核验引用。
5. 输出带依据、风险提示和免责声明的回答。

示例问题：

```text
公司拖欠工资三个月，员工是否可以立即解除劳动合同？
```

### 类案检索

入口：`IntentType.CASE_SEARCH`

流程：

1. 识别类案检索意图。
2. 调用 `ResearchAgent.search_cases`。
3. 通过外部 RAG API 检索案例。
4. 返回案号、法院、裁判日期、案由、裁判要旨、裁判结果等。

示例问题：

```text
帮我找建设工程领域关于实际施工人主张工程价款的案例
```

### 文书初稿生成

入口：`IntentType.DOCUMENT_DRAFT`

当前本地模板支持：

- 民事起诉状
- 答辩状

它会尝试从用户输入中提取原告、被告、事实与理由、诉讼请求等信息，并提示缺失材料。没有 LLM 时也能生成模板版初稿。

示例问题：

```text
生成一份民事起诉状
```

### 引用核验

工具：`CitationVerifyTool`

支持解析类似下面的引用：

```text
《劳动合同法》第38条
```

核验内容包括：

- 引用格式能否解析
- RAG 库中是否能匹配到条文
- 条文是否失效
- 引用内容是否准确

### 合同审查

入口：`IntentType.CONTRACT_REVIEW`

当前是 MVP 占位能力：

- 可以识别合同审查意图。
- 可以走合同条款检索入口。
- 完整合同审查逻辑仍待实现。

### 客户画像记忆库

模块：`law_agent.client_profiles`

用途：把每周更新的脱敏律师客户画像 JSON 导入 SQLite，作为项目后续的驱动引擎之一。

当前模板格式：

```text
律师客户画像_开发版_v4_含画像更新动作_cleaned_20260505_164732.json
```

导入后会生成：

```text
data/client_profiles.db
```

数据库包含三张表：

- `profile_import_batches`：每次 JSON 导入批次。
- `lawyer_client_profiles`：画像主表，一条 `record_id` 一条画像。
- `profile_update_events`：每周画像更新动作流水。

常用驱动字段会被展开成列：

- `matter_type`
- `stage`
- `conflict_structure`
- `role_pattern`
- `client_goal`
- `key_constraints`
- `first_judgment`
- `strategy_choice`
- `value_order`
- `risk_communication`
- `handling_temperature`
- `reusable_rule`
- `profile_update_action`

同时保留完整脱敏原始记录 `raw_record_json`，方便回放、调试和后续策略生成。

导入命令：

```powershell
.\.venv\Scripts\python.exe -m law_agent.client_profiles "律师客户画像_开发版_v4_含画像更新动作_cleaned_20260505_164732.json" --db data\client_profiles.db
```

导入是幂等的：同一个 `record_id` 会更新，不会重复插入画像主表；更新动作会进入流水表。

## 项目结构

```text
law_agent/
├── __init__.py
├── main.py                  # API / CLI / test 入口
├── orchestrator.py          # 主编排器
├── intent.py                # 意图识别
├── risk.py                  # 风险分级
├── audit.py                 # 审计日志
├── client_profiles.py       # 律师客户画像记忆库
├── storage_sqlmodel.py      # 审计/审阅/画像 SQLModel 迁移记录模型
├── logging_config.py        # loguru 日志配置
├── hierarchy/               # Hierarchical Orchestrator 任务、步骤、主管层
├── tools/
│   ├── base.py              # 工具基类和注册表
│   ├── rag_client.py        # 外部 RAG API 客户端
│   ├── regulation.py        # 法规检索工具
│   ├── case_search.py       # 类案检索工具
│   ├── citation.py          # 引用核验工具
│   └── document.py          # 文书生成工具
└── sub_agents/
    ├── research.py          # 法规/案例/合同条款研究子 Agent
    └── document_agent.py    # 文书子 Agent

config/
├── settings.py              # 应用配置
└── prompts/                 # Prompt 模板

tests/                       # 单元测试
data/                        # SQLite 数据库和运行数据
```

## 环境变量

复制配置模板：

```powershell
Copy-Item .env.example .env
```

主要配置项：

```text
RAG_API_ENDPOINT=http://localhost:8000
RAG_API_KEY=your_rag_api_key_here

ENABLE_EXTERNAL_SEARCH=false
TAVILY_API_KEY=tvly-your_api_key_here
TAVILY_PROJECT_ID=
BRAVE_SEARCH_API_KEY=your_brave_search_api_key_here
WEB_SEARCH_TIMEOUT=20
WEB_SEARCH_MAX_RESULTS=5
WEB_SEARCH_MAX_TOKENS=8192

LLM_PROVIDER=openai-compatible
# 旧的 LLM_API_KEY / LLM_API_ENDPOINT / LLM_MODEL 调用方式已冻结
MINIMAX_API_ENDPOINT=https://api.minimaxi.com/v1
MINIMAX_API_KEY=your_minimax_api_key_here
MINIMAX_MODEL=MiniMax-M2.7
MINIMAX_FALLBACK_MODELS=
LLM_TEMPERATURE=0.3
LLM_MAX_TOKENS=2000

AUDIT_DB_PATH=data/audit.db
TASK_DB_PATH=data/tasks.db
CLIENT_PROFILE_DB_PATH=data/client_profiles.db
ORCHESTRATION_DB_PATH=data/orchestration.db

ALIYUN_DASHSCOPE_API_KEY=your_dashscope_api_key_here
ALIYUN_KNOWLEDGE_BASE_ID=your_knowledge_base_id_here
ALIYUN_OSS_BUCKET=your_oss_bucket_here
DATABASE_URL=postgresql://user:password@host:5432/law_agent
REDIS_URL=redis://host:6379/0

ENVIRONMENT=development
```

`.env.example` 里也有飞书和 OpenClaw 相关配置，但当前代码中还没有完整接入实现。

## 安装依赖

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

如果没有虚拟环境，也可以先创建：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 运行方式

### 命令行交互

```powershell
.\.venv\Scripts\python.exe -m law_agent.main cli
```

### API 服务

```powershell
.\.venv\Scripts\python.exe -m law_agent.main api
```

默认地址：

```text
http://localhost:8000
```

接口：

```text
GET  /api/v1/health
GET  /api/v1/stats
POST /api/v1/process
POST /api/v1/tasks
GET  /api/v1/tasks/{task_id}
GET  /api/v1/tasks/{task_id}/steps
POST /api/v1/files/upload
POST /api/v1/research/web
POST /api/v1/profiles/import
GET  /api/v1/profiles
GET  /api/v1/profiles/{record_id}
GET  /api/v1/audit
GET  /api/v1/audit/external-actions
GET  /api/v1/review/tasks
POST /api/v1/review/confirm
POST /api/v1/review/reject
POST /api/v1/export
POST /api/v1/send
GET  /workbench
```

中高风险输出在 `/process` 中会返回 `can_export=false`，必须经 `/review/confirm` 人工确认后，才能通过 `/export` 或 `/send` 记录对外动作；确认前内容、确认后内容、确认人、确认时间和命中的画像规则会写入审计明细。

Web 工作台入口：`http://localhost:8000/workbench`。工作台可提交处理请求、查看风险和 trace_id、查看画像策略、查询审计记录，并完成确认、驳回、修改后确认、导出或发送留痕。处理完成后会自动读取 `/api/v1/tasks/{task_id}`，展示层级编排任务、步骤状态、每步工具调用和失败原因。当前工作台按单用户开发模式运行，界面提供“切换用户”入口但默认固定使用 `web_user` / `web_session`；后续接入登录态或团队用户列表时，可从该入口扩展多用户切换。

工作台已预置轻量核心指令，输入框直接输入或点击指令按钮均可执行：

|指令|用途|
|---|---|
|`/help`|查看帮助引导|
|`/clear`|清理当前页面缓存|
|`/new`|新建一次空白处理|
|`/review`|加载待审阅任务|
|`/examples`|查看输入示例|
|`/status`|查看服务与模型状态|
|`/search <问题>`|普通联网检索|
|`/research <问题>`|深度联网研究，优先使用 Tavily Research|
|`/extract <URL> [问题]`|读取指定网页正文|
|`/site <URL或域名> <主题>`|发现或采集指定站点资料|

请求示例：

```json
{
  "user_input": "公司拖欠工资三个月，员工是否可以立即解除劳动合同？",
  "session_id": "session_123",
  "user_id": "user_456"
}
```

显式联网研究请求示例：

```json
{
  "query": "最高人民法院 建设工程 实际施工人 工程价款",
  "purpose": "legal_source_check",
  "providers": ["tavily", "brave"],
  "max_results": 5,
  "freshness": "month",
  "include_domains": ["court.gov.cn"],
  "exclude_domains": []
}
```

`/api/v1/research/web` 支持的 `purpose` 包括：

```text
quick_search       普通来源发现
deep_research      深度研究
extract_url        指定 URL 正文提取
site_discovery     站点页面发现
site_crawl         站点批量采集
news_check         新闻和近期动态
legal_source_check 法规、案例、政策来源补强
place_or_entity    地点、机构、实体查询
```

联网研究工具会按任务目的组合调用 Tavily Search / Extract / Map / Crawl / Research 和 Brave LLM Context / Web / News。联网资料默认只作为内部研究线索，不会写入“已核验法律依据”；中高风险输出仍走人工审阅和导出/发送门禁。

## Hierarchical Orchestrator

当前后端已开始从单层 `LawOrchestrator` 迁移到 Hierarchical 模式。`/api/v1/process` 仍保持原响应格式，但内部会创建一条层级编排任务，记录 intent、profile、supervisor、risk 等步骤。

层级结构：

```text
RootOrchestrator
├── WorkflowPlanner
├── SupervisorOrchestrator
│   ├── ResearchSupervisor
│   ├── DocumentSupervisor
│   └── ReviewSupervisor
└── OrchestrationStore
    ├── OrchestrationTask
    ├── OrchestrationStep
    └── ToolCallRecord
```

新增任务接口：

```text
POST /api/v1/tasks
```

请求体与 `/api/v1/process` 相同：

```json
{
  "user_input": "帮我找建设工程实际施工人主张工程价款的类案",
  "session_id": "session_123",
  "user_id": "user_456"
}
```

返回包含兼容处理结果和层级任务：

```json
{
  "task": {
    "task_id": "task-id",
    "trace_id": "trace-id",
    "status": "completed",
    "steps": [],
    "tool_calls": []
  },
  "result": {
    "success": true,
    "output": "..."
  }
}
```

可以用 `GET /api/v1/tasks/{task_id}` 查询任务、步骤和工具调用，用 `GET /api/v1/tasks/{task_id}/steps` 只查询步骤列表。文件上传入口为 `POST /api/v1/files/upload`，字段为 multipart `file` 和可选 `trace_id`，文件会保存到 `data/uploads/`。

配置说明：

- `ORCHESTRATION_DB_PATH` 控制层级任务库路径，默认 `data/orchestration.db`。
- 配置读取已迁移到 `pydantic-settings`，仍兼容现有 `.env` 变量名。
- 任务模型优先使用 SQLModel；在尚未安装 `sqlmodel` 的开发环境中会回退到 SQLite 适配层，安装依赖后自动使用 SQLModel。
- `AuditLogger` 和 `ReviewTaskStore` 已增加 SQLModel 适配层，运行时会在依赖可用时使用同名表读写旧 SQLite 文件；客户画像库已提供 SQLModel 迁移计划，MVP 阶段继续以 sqlite3 导入逻辑为准。

### 内置样例

```powershell
.\.venv\Scripts\python.exe -m law_agent.main test
```

### Docker

```powershell
docker compose up --build
```

`docker-compose.yml` 里包含：

- `law-agent`：主应用
- `prometheus`：监控，预留
- `grafana`：可视化，预留

## 测试

当前建议关闭 pytest cache provider，避免本地权限问题干扰测试结果：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_client_profiles.py tests\test_intent.py tests\test_risk.py tests\test_audit.py -q -p no:cacheprovider
```

最近一次验证结果：

```text
17 passed, 8 warnings
```

## 代码使用示例

### 意图识别

```python
from law_agent.intent import IntentRecognizer

recognizer = IntentRecognizer()
result = await recognizer.recognize("帮我找建设工程领域的案例")

print(result.intent)
print(result.confidence)
```

### 风险分级

```python
from law_agent.intent import IntentType
from law_agent.risk import RiskLabeler

labeler = RiskLabeler()
level = await labeler.label(
    intent=IntentType.DOCUMENT_DRAFT,
    content="生成一份民事起诉状",
)

print(level)
```

### 客户画像查询

```python
from law_agent.client_profiles import ClientProfileStore

store = ClientProfileStore("data/client_profiles.db")

profiles = store.list_driver_profiles(
    matter_type="民事合同",
    stage="咨询",
    ingestion_level="A核心画像",
)

for profile in profiles:
    print(profile["strategy_choice"])
    print(profile["risk_communication"])
```

## 当前限制

- 已接入 OpenAI 兼容模式 LLM 客户端；当前可用于意图辅助识别、文书初稿生成和法规检索结果总结。
- RAG API 需要外部服务提供；本项目只实现客户端调用和结果转换，尚未接入阿里云百炼知识库或 DashVector。
- 飞书入口目前只有环境变量模板，还没有完整机器人接入代码。
- 合同审查还处于占位实现，适合继续扩展。
- 文书生成已支持 LLM 增强，模型失败时会自动退回模板生成。
- 客户画像库已经接入 `LawOrchestrator` 的基础决策链路，当前已规划 SQLModel 迁移模型，但导入写入仍是本地 SQLite / 规则匹配版本；云端正式版应迁移到 RDS PostgreSQL。
- 云端部署、HTTPS、监控告警、备份恢复、密钥管理尚未实现。

## 建议下一步

1. 接入 OpenClaw Skill 层。
2. 接入阿里云百炼知识库或 DashVector，形成可更新的法律专业知识库。
3. 保持旧 LLM 调用方式冻结，优先完善 MiniMax 调用、审计与失败降级。
4. 将客户画像导入链路迁移到 SQLModel，再统一切换到 RDS PostgreSQL。
5. 部署 ECS + Docker Compose + Nginx + HTTPS 的 MVP 云端版本。
6. 增加知识库更新任务：OSS 上传、文档清洗、分块、元数据标注、导入、审计。
7. 增加监控、日志、告警、备份和恢复策略。

## 许可证

MIT License
