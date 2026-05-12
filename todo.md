# Law Agent x OpenClaw 施工路线树形清单

> 总原则：先固化 Law Agent 后端闭环，再让 OpenClaw 作为外层运行时调用。OpenClaw 不接管法律核心判断，只负责接入、调度、通知和自动化任务。

## 0. 边界定义

- [x] 保留 `LawOrchestrator` 作为法律业务核心
- [x] 保留 `RiskLabeler` 作为风险门禁
- [x] 保留 `AuditLogger` 作为合规留痕
- [x] 保留 `ClientProfileStore` 作为客户画像记忆库
- [ ] 明确 OpenClaw 只负责：
  - [ ] 消息接入
  - [ ] 定时任务
  - [ ] 调用后端 API
  - [ ] 任务分发
  - [ ] 通知人工审阅

## 1. 后端 API 固化

- [x] 已有基础 API
  - [x] `GET /api/v1/health`
  - [x] `GET /api/v1/stats`
  - [x] `POST /api/v1/process`
- [x] 补齐画像 API
  - [x] `POST /api/v1/profiles/import`
  - [x] `GET /api/v1/profiles`
  - [x] `GET /api/v1/profiles/{record_id}`
- [x] 补齐审计 API
  - [x] `GET /api/v1/audit`
- [x] 扩展 `/process` 标准响应
  - [x] `trace_id`
  - [x] `risk_level`
  - [x] `requires_human_review`
  - [x] `tools_used`
  - [x] `profile_record_ids`
  - [x] `review_status`
- [x] 修正审计日志摘要
  - [x] `input_summary` 记录用户输入摘要
  - [x] `output_summary` 记录模型输出摘要

## 2. 画像驱动编排

- [x] 已有 `ClientProfileStore`
- [x] 已能导入画像 JSON 到 `data/client_profiles.db`
- [x] 已支持按字段查询画像
- [x] 给 `LawOrchestrator` 注入 `ClientProfileStore`
- [x] 在意图识别后抽取画像匹配字段
  - [x] `matter_type`
  - [x] `stage`
  - [x] `client_goal`
  - [x] `first_judgment`
  - [x] `ingestion_level`
- [x] 将命中画像写入处理上下文
  - [x] `profile_record_ids`
  - [x] `strategy_choice`
  - [x] `risk_communication`
  - [x] `handling_temperature`
  - [x] `reusable_rule`
- [x] 输出中体现画像策略
  - [x] 是否建议先补证据
  - [x] 是否适合生成对外文书
  - [x] 风险沟通方式
  - [x] 文书语气和处理温度
- [x] 审计日志记录使用过的画像规则

## 3. 风控与人工审阅闭环

- [x] 已有 `RiskLevel`
  - [x] `LOW`
  - [x] `MEDIUM`
  - [x] `HIGH`
- [x] 已有 `RiskResult`
  - [x] `requires_confirmation`
  - [x] `can_export`
  - [x] 接入 `/process` 返回值
- [x] 增加统一风控策略
  - [x] `LOW`：可直接内部参考
  - [x] `MEDIUM`：需要律师确认后可对外
  - [x] `HIGH`：必须人工审阅，不允许自动发送
- [x] 增加审阅任务模型
  - [x] `trace_id`
  - [x] `review_status`
  - [x] `original_output`
  - [x] `reviewed_output`
  - [x] `reviewer_id`
  - [x] `reviewed_at`
- [x] 增加人工审阅 API
  - [x] `POST /api/v1/review/confirm`
  - [x] `POST /api/v1/review/reject`
- [x] 所有对外发送或导出动作写入审计
  - [x] 谁确认
  - [x] 何时确认
  - [x] 确认前内容
  - [x] 确认后内容
  - [x] 使用了哪些画像规则
  - [x] `POST /api/v1/export`
  - [x] `POST /api/v1/send`
  - [x] `GET /api/v1/audit/external-actions`

## 4. Web 工作台 MVP

- [x] 做一个最小可用 Web 工作台
  - [x] 查看处理结果
  - [x] 查看风险等级
  - [x] 查看 trace_id
  - [x] 查看命中的画像规则
  - [x] 查看审计记录
- [x] 支持人工审阅
  - [x] 确认
  - [x] 驳回
  - [x] 修改后确认
- [x] 高风险内容默认不展示为“可直接发送”状态
- [x] 工作台用户入口改为单用户切换按钮
  - [x] 当前固定 `web_user` / `web_session`
  - [x] 预留多用户切换模块接入点
  - [x] 隐藏开发期裸露的 `user_id` / `session_id` 输入框
- [x] 预置 MVP 核心指令
  - [x] `/help`：提供帮助引导
  - [x] `/clear`：清理当前页面缓存
  - [x] `/new`：新建一次空白处理
  - [x] `/review`：加载待审阅任务
  - [x] `/examples`：查看输入示例
  - [x] `/status`：查看服务与模型状态

## 5. OpenClaw Skill 层

- [ ] 所有 Skill 只调用 FastAPI，不直接读写数据库
- [ ] 定义 `law_process`
  - [ ] 调用 `/api/v1/process`
  - [ ] 返回草稿或待审阅结果
- [ ] 定义 `law_profile_import`
  - [ ] 调用 `/api/v1/profiles/import`
- [ ] 定义 `law_profile_search`
  - [ ] 调用 `/api/v1/profiles`
- [ ] 定义 `law_audit_query`
  - [ ] 调用 `/api/v1/audit`
- [ ] 定义 `law_review_notify`
  - [ ] 推送高风险任务给律师审阅
- [ ] 高风险结果禁止由 OpenClaw 自动发送给客户

## 6. Gateway 接入

- [ ] 接入优先级
  - [ ] Web 前端
  - [ ] 飞书
  - [ ] 企业微信或钉钉
  - [ ] Telegram / Slack 可选
- [ ] 统一入口请求格式
  - [ ] `user_input`
  - [ ] `user_id`
  - [ ] `session_id`
  - [ ] `channel`
- [ ] 统一返回格式
  - [ ] `risk_level`
  - [ ] `review_status`
  - [ ] `trace_id`
- [ ] 高风险消息只返回审阅提示
  - [ ] “已生成草稿，请进入工作台审阅”
  - [ ] 不直接返回完整法律意见

## 7. 定时任务与画像周更

- [ ] 约定每周画像 JSON 放置路径
- [ ] OpenClaw 定时任务每周执行
  - [ ] 检查新 JSON 文件
  - [ ] 调用 `law_profile_import`
  - [ ] 写入导入批次
  - [ ] 生成导入报告
- [ ] 导入报告包含
  - [ ] 扫描记录数
  - [ ] 入库记录数
  - [ ] 跳过记录数
  - [ ] 需要人工复核数
  - [ ] 本周强化/削弱/新增规则数量
- [ ] 报告推送给律师或管理员

## 8. 云端部署与 7x24 运维

- [ ] 明确部署路线
  - [ ] MVP：ECS + Docker Compose + Nginx + HTTPS
  - [ ] 低运维备选：SAE 镜像部署
  - [ ] 企业级扩展：ACK / Kubernetes
- [ ] 配置云端基础设施
  - [ ] ECS 或 SAE 应用运行环境
  - [ ] 域名和 HTTPS 证书
  - [ ] Nginx 反向代理或云产品网关
  - [ ] 环境变量和密钥管理
- [ ] 接入云端持久化组件
  - [ ] RDS PostgreSQL：业务数据、画像、审计、审阅任务
  - [ ] OSS：知识库源文件、上传文件、导出文书归档
  - [ ] Redis / Tair 可选：短期会话缓存、任务状态缓存
- [ ] 增加 7x24 运维能力
  - [ ] 服务健康检查
  - [ ] 结构化日志
  - [ ] 监控指标
  - [ ] 异常告警
  - [ ] 数据备份和恢复策略

## 9. 阿里云知识库与记忆库集成

- [~] 接入阿里云模型与应用能力
  - [x] 先接入 OpenAI 兼容模式 LLM 客户端
  - [x] DashScope / 百炼 LLM 客户端
  - [ ] 百炼应用调用
  - [ ] API Key 和知识库 ID 配置
- [ ] 建设法律专业知识库
  - [ ] MVP：接入阿里云百炼知识库
  - [ ] 进阶：按需接入 DashVector 自建向量检索
  - [ ] 支持法规、司法解释、案例、合同模板、内部研究资料
- [ ] 设计知识库元数据 schema
  - [ ] `source_type`
  - [ ] `jurisdiction`
  - [ ] `authority_level`
  - [ ] `effective_date`
  - [ ] `expire_date`
  - [ ] `source_url`
  - [ ] `version`
  - [ ] `uploaded_by`
  - [ ] `review_status`
- [ ] 实现知识库更新流水线
  - [ ] 上传源文件到 OSS
  - [ ] 文档清洗
  - [ ] 分块
  - [ ] 元数据标注
  - [ ] 写入百炼知识库或 DashVector
  - [ ] 生成知识库版本号
  - [ ] 写入审计日志
- [ ] 记忆系统分层
  - [ ] Session Memory：当前会话上下文
  - [ ] Profile Memory：律师画像、客户画像、处理策略
  - [ ] Knowledge Memory：法律知识、案例、模板、内部资料
- [ ] 客户画像云端化
  - [ ] 将 `ClientProfileStore` 从 SQLite 迁移到 RDS PostgreSQL
  - [ ] 保留结构化字段查询优先
  - [ ] 暂不把律师画像混入法律知识库
  - [ ] 人工确认后再沉淀长期画像规则

## 最终架构树

```text
用户 / 律师
└── Web / 飞书 / API / 其他消息入口
    └── OpenClaw Gateway
        └── OpenClaw Agent Core
            └── OpenClaw Skills
                └── FastAPI Law Agent
                    └── LawOrchestrator
                        ├── IntentRecognizer
                        ├── ClientProfileStore
                        ├── ResearchAgent
                        ├── DocumentAgent
                        ├── RiskLabeler
                        └── AuditLogger
                            ├── 阿里云百炼 / DashScope
                            ├── 法律知识库：百炼知识库 / DashVector
                            ├── 业务数据库：RDS PostgreSQL
                            ├── 文件归档：OSS
                            └── 人工审阅 / 对外发送 / 审计追踪
```

## 立即开干优先级

1. [x] 扩展 `/process` 返回 `requires_human_review`、`profile_record_ids`、`review_status`
2. [x] 把 `ClientProfileStore` 注入 `LawOrchestrator`
3. [x] 补齐画像导入和查询 API
4. [x] 补齐审计查询 API，并修正 `input_summary`
5. [x] 增加人工审阅任务和 confirm/reject 闭环
6. [x] 补齐对外发送 / 导出 API 与审计留痕
7. [x] 接入 OpenAI 兼容模式 LLM
8. [x] 完成 Hierarchical Orchestrator 架构重构与 SQLModel 迁移
    - [x] Phase 1: 依赖与配置基础 (使用 uvicorn[standard], pydantic-settings, sqlmodel 等)
    - [x] Phase 2: 任务与步骤模型 (OrchestrationTask, OrchestrationStep, ToolCallRecord 等)
    - [x] Phase 3: Hierarchical Orchestrator (RootOrchestrator, WorkflowPlanner, 各 Supervisor 等)
    - [x] Phase 4: API 与工作台 (新的 /api/v1/tasks 接口与模板化支持)
    - [x] Phase 5: 存储迁移 (AuditLogger, ReviewTaskStore 迁移至 SQLModel)
    - [x] Phase 6: 测试与验证 (各项 CRUD 和流程调用的兼容性测试)
9. [x] 接入阿里云百炼 / DashScope LLM
10. [ ] 接入可更新的法律专业知识库
11. [ ] 规划 ECS + Docker Compose 云端 MVP 部署
