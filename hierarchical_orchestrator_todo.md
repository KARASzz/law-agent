# TODO: Hierarchical Orchestrator 架构转型

## Phase 1: 依赖与配置基础
- [x] 更新 requirements.txt
  - [x] 使用 uvicorn[standard]
  - [x] 新增 python-multipart
  - [x] 新增 jinja2
  - [x] 新增 pydantic-settings
  - [x] 新增 sqlmodel
- [x] 用 pydantic-settings 替换当前手写环境变量解析
- [x] 保留现有 .env / .env.example 使用方式
- [x] 增加 SQLModel engine/session 初始化
- [x] 引入 loguru 统一运行日志

## Phase 2: 任务与步骤模型
- [x] 新增 OrchestrationTask
- [x] 新增 OrchestrationStep
- [x] 新增 ToolCallRecord
- [x] 新增 AgentResult
- [x] 用 SQLModel 保存任务状态、步骤状态、工具调用记录
- [x] 保持旧 /api/v1/process 返回格式兼容

## Phase 3: Hierarchical Orchestrator
- [x] 新增 RootOrchestrator
- [x] 新增 WorkflowPlanner
- [x] 新增 SupervisorOrchestrator
- [x] 新增 ResearchSupervisor
- [x] 新增 DocumentSupervisor
- [x] 新增 ReviewSupervisor
- [x] 复用现有 ResearchAgent
- [x] 复用现有 DocumentAgent
- [x] 复用现有 RiskLabeler
- [x] 复用现有 ExternalResearchTool
- [x] 将原 LawOrchestrator._route_intent() 逐步迁移到 planner + supervisor

## Phase 4: API 与工作台
- [x] 新增 POST /api/v1/tasks
- [x] 新增 GET /api/v1/tasks/{task_id}
- [x] 新增 GET /api/v1/tasks/{task_id}/steps
- [x] 新增文件上传接口，使用 python-multipart
- [x] 为后续工作台模板化接入 Jinja2Templates
- [x] 工作台后续展示任务层级、步骤状态、工具调用和失败原因

## Phase 5: 存储迁移
- [x] 为 AuditLogger 增加 SQLModel 适配层
- [x] 为 ReviewTaskStore 增加 SQLModel 适配层
- [x] 为 ClientProfileStore 规划 SQLModel 迁移
- [x] 迁移期间保留旧 SQLite 表兼容
- [x] 将 tools_used 从逗号字符串升级为结构化工具调用记录

## Phase 6: 测试
- [x] 测试 settings 环境变量解析
- [x] 测试 SQLModel task/step/tool_call CRUD
- [x] 测试每个 intent 生成正确 workflow
- [x] 测试 supervisor 调用正确 worker
- [x] 测试 /api/v1/process 兼容旧响应
- [x] 测试 /api/v1/tasks 创建和查询任务
- [x] 测试工具失败时记录错误和任务状态
- [x] 测试中高风险仍进入人工审阅
- [x] 运行 python3 -m pytest -q -p no:cacheprovider
