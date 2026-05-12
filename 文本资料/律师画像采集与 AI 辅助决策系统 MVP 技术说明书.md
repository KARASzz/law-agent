# Law Agent x OpenClaw 法律 AI 工作流系统 MVP 技术说明书

版本：v0.2  
状态：当前工程基线  
维护人：项目维护人  
适用对象：律师团队 / 技术开发团队 / 合规审查人员 / OpenClaw 集成方  
最后更新：2026-05-07

---

## 0. 一句话定义

本系统是一个面向律师执业流的法律 AI 工作流后端。它以 `Law Agent FastAPI` 为法律业务核心，把法律问题处理、客户画像调用、风险分级、人工审阅、导出/发送审计组织成可追踪的闭环；后续由 OpenClaw 作为外层运行时负责消息接入、任务调度、通知和自动化调用。

系统不替代律师判断，不自动发送高风险法律意见，不把律师画像当作法律依据。

---

## 1. 当前 MVP 定位

### 1.1 旧版定位

旧版说明书主要描述的是：

```text
Excel 脱敏采集表
+ Python 清洗脚本
+ JSON 画像数据
+ 人工定期清洗入库
```

这部分仍可作为画像采集的数据来源，但已经不是当前系统的完整 MVP。

### 1.2 当前定位

当前 MVP 已升级为：

```text
FastAPI Law Agent
+ LawOrchestrator
+ ClientProfileStore
+ RiskLabeler
+ ReviewTaskStore
+ AuditLogger
+ 人工审阅 / 导出发送审计闭环
```

当前重点不是单纯“采集画像”，而是先固化法律 AI 后端闭环：

- 接收法律任务；
- 识别意图；
- 调用客户画像策略；
- 生成内部参考输出；
- 标记风险等级；
- 对中高风险任务创建人工审阅任务；
- 只有确认后的内容才能导出或对外发送；
- 所有关键动作写入审计。

---

## 2. 核心边界

### 2.1 Law Agent 与 OpenClaw 的边界

总原则：

```text
Law Agent 负责法律业务核心判断与合规闭环。
OpenClaw 负责外层接入、调度、通知和自动化执行。
```

OpenClaw 不直接读写数据库，不接管法律判断，不绕过风控门禁。

OpenClaw 只负责：

- 消息接入；
- 定时任务；
- 调用 FastAPI；
- 任务分发；
- 通知人工审阅；
- 根据 API 返回结果决定是否展示完整内容。

### 2.2 画像库与知识库的边界

```text
Profile Memory 解决：这个案件应如何沟通、如何处理、是否适合推进。
Knowledge Memory 解决：法律依据、法规、案例、模板在哪里。
```

画像库不得被包装成法律依据；法律知识库也不应存储律师个人策略偏好。

### 2.3 输出边界

系统输出分三类：

|类型|处理方式|
|---|---|
|低风险内部参考|可直接展示给律师内部参考|
|中风险内容|需律师确认后才可对外使用|
|高风险内容|必须人工审阅，不允许自动发送|

任何对外发送或导出动作，都必须经过 API 门禁并写入审计。

---

## 3. 当前系统架构

### 3.1 运行架构

```text
用户 / 律师 / 助理
└── Web / 飞书 / API / 其他消息入口
    └── OpenClaw Gateway（规划中）
        └── OpenClaw Skills（规划中）
            └── FastAPI Law Agent
                ├── LawOrchestrator
                ├── IntentRecognizer
                ├── ClientProfileStore
                ├── ResearchAgent
                ├── DocumentAgent
                ├── RiskLabeler
                ├── ReviewTaskStore
                └── AuditLogger
```

### 3.2 当前代码模块

|模块|当前状态|说明|
|---|---|---|
|`law_agent/main.py`|已实现|FastAPI 应用、API 路由、应用生命周期|
|`law_agent/orchestrator.py`|已实现|法律任务主编排器|
|`law_agent/intent.py`|已实现|意图识别|
|`law_agent/client_profiles.py`|已实现|SQLite 客户画像记忆库|
|`law_agent/risk.py`|已实现|风险分级与导出门禁字段|
|`law_agent/review.py`|已实现|人工审阅任务存储|
|`law_agent/audit.py`|已实现|主审计日志与外发/导出审计|
|`law_agent/sub_agents/research.py`|已实现骨架|法规、案例、条款检索代理|
|`law_agent/sub_agents/document_agent.py`|已实现骨架|文书草稿与合同审查代理|
|`law_agent/tools/*`|已实现骨架|RAG、法规、案例、引用、文书工具|

### 3.3 当前数据存储

MVP 阶段使用本地 SQLite：

|数据库|用途|
|---|---|
|`data/client_profiles.db`|客户画像主表与画像更新动作流水|
|`data/audit.db`|任务审计、导出/发送审计|
|`data/tasks.db`|人工审阅任务|

云端正式版计划迁移到 RDS PostgreSQL，并接入 OSS、Redis / Tair 等组件。

---

## 4. 已实现 API

### 4.1 基础接口

```text
GET  /api/v1/health
GET  /api/v1/stats
POST /api/v1/process
```

`POST /api/v1/process` 请求格式：

```json
{
  "user_input": "生成一份民事起诉状",
  "session_id": "session_001",
  "user_id": "user_001"
}
```

标准响应包含：

```json
{
  "success": true,
  "task_id": "task-id",
  "trace_id": "trace-id",
  "output": "系统输出",
  "intent": "document_draft",
  "risk_level": "high",
  "confidence": 0.9,
  "tools_used": [],
  "requires_human_review": true,
  "can_export": false,
  "profile_record_ids": [],
  "profile_strategy": {},
  "review_status": "pending_review",
  "review_task": {},
  "processing_time": 0.01,
  "error": null
}
```

### 4.2 画像接口

```text
POST /api/v1/profiles/import
GET  /api/v1/profiles
GET  /api/v1/profiles/{record_id}
```

画像导入当前接受服务器本地 JSON 文件路径：

```json
{
  "json_file_path": "律师客户画像_开发版_v4_含画像更新动作_cleaned_20260505_164732.json"
}
```

画像查询支持按以下字段过滤：

- `matter_type`
- `stage`
- `first_judgment`
- `ingestion_level`
- `limit`

### 4.3 审计接口

```text
GET /api/v1/audit
GET /api/v1/audit/external-actions
```

主审计日志记录：

- `task_id`
- `session_id`
- `trace_id`
- `user_id`
- `intent`
- `input_summary`
- `output_summary`
- `tools_used`
- `risk_level`
- `confirmed`
- `exported`
- `timestamp`

导出/发送审计记录：

- 谁执行动作；
- 动作类型：`export` 或 `send`；
- 风险等级；
- 审阅状态；
- 谁确认；
- 何时确认；
- 确认前内容；
- 确认后内容；
- 使用了哪些画像规则；
- 发送目标或导出位置。

### 4.4 人工审阅接口

```text
POST /api/v1/review/confirm
POST /api/v1/review/reject
```

确认请求：

```json
{
  "trace_id": "trace-id",
  "reviewer_id": "lawyer_001",
  "reviewed_output": "律师修改确认后的内容"
}
```

驳回请求：

```json
{
  "trace_id": "trace-id",
  "reviewer_id": "lawyer_001",
  "rejection_reason": "事实不足，暂不适合对外使用"
}
```

### 4.5 导出与发送接口

```text
POST /api/v1/export
POST /api/v1/send
```

导出请求：

```json
{
  "trace_id": "trace-id",
  "actor_id": "assistant_001",
  "export_format": "markdown",
  "destination": "case-folder"
}
```

发送请求：

```json
{
  "trace_id": "trace-id",
  "actor_id": "assistant_001",
  "destination": "client@example.com"
}
```

门禁规则：

- 低风险：允许导出或发送，并写入审计；
- 中风险：必须先确认；
- 高风险：必须先确认；
- 待审阅：禁止导出或发送；
- 已驳回：禁止导出或发送；
- 无审计记录：禁止导出或发送。

---

## 5. 画像驱动编排

### 5.1 当前画像来源

当前系统可导入脱敏后的律师客户画像 JSON，并写入 `ClientProfileStore`。

导入后形成：

- 画像主表；
- 画像更新动作流水；
- 可被编排器检索的结构化字段。

### 5.2 当前匹配字段

`LawOrchestrator` 在意图识别后，会从用户输入中抽取轻量匹配字段：

- `matter_type`
- `stage`
- `client_goal`
- `first_judgment`
- `ingestion_level`

### 5.3 当前写入上下文的画像策略

命中画像后，系统会把以下信息写入处理上下文和响应：

- `profile_record_ids`
- `strategy_choice`
- `risk_communication`
- `handling_temperature`
- `reusable_rule`
- `external_document_suitability`

输出中会追加 `【画像策略】`，用于提示律师：

- 是否建议先补证据；
- 是否适合生成对外文书；
- 风险沟通方式；
- 文书语气和处理温度；
- 可复用规则。

### 5.4 当前边界

画像策略只作为内部辅助，不构成法律依据。

正式法律依据仍应来自：

- 法律法规；
- 司法解释；
- 案例；
- 合同模板；
- 律所内部审核通过的知识材料。

---

## 6. 风控与人工审阅闭环

### 6.1 风险等级

当前系统使用三档风险：

|等级|含义|默认处理|
|---|---|---|
|`low`|一般法律信息整理|可内部参考|
|`medium`|类案分析、合同条款建议等|需律师确认后可对外|
|`high`|诉讼策略、文书、期限判断等|必须人工审阅|

### 6.2 风控字段

`RiskResult` 包含：

- `level`
- `message`
- `requires_confirmation`
- `can_export`

当前策略：

```text
low: requires_confirmation=false, can_export=true
medium: requires_confirmation=true, can_export=false
high: requires_confirmation=true, can_export=false
```

### 6.3 审阅任务模型

审阅任务字段：

- `trace_id`
- `task_id`
- `session_id`
- `user_id`
- `intent`
- `risk_level`
- `review_status`
- `original_output`
- `reviewed_output`
- `reviewer_id`
- `reviewed_at`
- `rejection_reason`
- `created_at`
- `updated_at`

审阅状态：

|状态|含义|
|---|---|
|`pending_review`|等待人工审阅|
|`confirmed`|已确认，可进入导出/发送门禁|
|`rejected`|已驳回，禁止对外使用|
|`not_required`|低风险，无需审阅|

### 6.4 对外动作闭环

```text
/process
↓
RiskLabeler 标记风险
↓
中高风险创建 review_task
↓
律师 confirm / reject
↓
confirm 后允许 export / send
↓
AuditLogger 写入主审计 + external_action_logs
```

---

## 7. 数据采集与脱敏

### 7.1 采集对象

采集对象不是案件事实，而是律师的判断行为：

- 冲突结构；
- 第一判断；
- 判断理由；
- 策略选择；
- 价值排序；
- 风险沟通方式；
- 处理温度；
- 可复用规则；
- 阶段性复盘。

### 7.2 禁止采集内容

严禁采集：

- 当事人姓名；
- 身份证号；
- 联系方式；
- 案号；
- 法院名称；
- 公司名称；
- 具体金额；
- 具体合同原文；
- 具体证据原文；
- 医疗、家庭、刑事等高度敏感细节；
- 能够反推出具体案件身份的信息。

### 7.3 入库前检查

每条画像记录入库前必须确认：

```text
1. 是否已经脱敏？
2. 是否没有案件可识别信息？
3. 是否抽象成行为逻辑？
4. 是否能沉淀为判断规则？
5. 是否有复盘反馈？
6. 是否能说明适用条件或反例边界？
```

### 7.4 不入库规则

以下记录不入库：

- 含有真实案件身份信息；
- 仅描述案件事实，没有判断逻辑；
- 仅记录情绪，没有策略意义；
- 无法抽象成可复用规则；
- 无法判断是否脱敏；
- 违反律师保密义务；
- 存在高度敏感信息且无法处理。

---

## 8. 记忆系统分层

### 8.1 Session Memory

用途：当前会话上下文，短期有效。

MVP 状态：暂未实现独立会话记忆库。  
后续方案：先存 RDS PostgreSQL 的 `sessions/messages` 表，并发上来后可加 Redis / Tair。

### 8.2 Profile Memory

用途：律师画像、客户画像、办案策略、风险沟通偏好。

MVP 状态：已实现 `ClientProfileStore`，当前使用 SQLite。  
后续方案：迁移到 RDS PostgreSQL，保留结构化字段查询优先。

### 8.3 Knowledge Memory

用途：法律知识、法规、案例、模板、内部研究资料。

MVP 状态：RAG 客户端与工具层已有骨架，但真实知识库尚未接入。  
后续方案：优先接入阿里云百炼知识库，进阶可接 DashVector。

---

## 9. 阿里云与知识库规划

### 9.1 模型调用

当前已先接入 OpenAI 兼容模式 LLM 客户端，用于意图辅助识别、文书初稿生成和法规检索结果总结。后续计划切换或扩展到：

- DashScope / 百炼 LLM 客户端；
- 百炼应用调用；
- API Key 与知识库 ID 配置；
- 可版本化的 Prompt。

### 9.2 法律知识库

知识库可包括：

- 法律法规；
- 司法解释；
- 指导案例；
- 类案裁判规则；
- 合同模板；
- 律所内部研究资料；
- 标准服务产品文档。

### 9.3 元数据 schema

知识库条目建议保留：

```text
source_type
jurisdiction
authority_level
effective_date
expire_date
source_url
version
uploaded_by
review_status
```

### 9.4 更新流水线

```text
法律文件 / 法规 / 案例 / 内部模板
↓
上传到 OSS
↓
文档清洗
↓
分块
↓
元数据标注
↓
写入百炼知识库或 DashVector
↓
生成知识库版本号
↓
写入审计日志
```

---

## 10. OpenClaw 集成规划

### 10.1 Skill 原则

所有 OpenClaw Skill 只调用 FastAPI，不直接读写数据库。

规划 Skill：

|Skill|调用接口|说明|
|---|---|---|
|`law_process`|`POST /api/v1/process`|处理法律任务|
|`law_profile_import`|`POST /api/v1/profiles/import`|导入画像 JSON|
|`law_profile_search`|`GET /api/v1/profiles`|查询画像|
|`law_audit_query`|`GET /api/v1/audit`|查询审计|
|`law_review_notify`|后续工作台/通知接口|推送高风险任务给律师|

### 10.2 Gateway 返回边界

统一入口请求格式：

```json
{
  "user_input": "用户输入",
  "user_id": "user_001",
  "session_id": "session_001",
  "channel": "web"
}
```

统一返回关键字段：

- `risk_level`
- `review_status`
- `trace_id`
- `requires_human_review`
- `can_export`

高风险消息不得直接返回完整法律意见给客户，应返回：

```text
已生成草稿，请进入工作台审阅。
```

---

## 11. Web 工作台 MVP

当前已提供 `/workbench` 单页工作台，用于处理请求、查看风险和审计，并完成人工审阅。

### 11.1 查看能力

工作台已支持：

- 查看处理结果；
- 查看风险等级；
- 查看 `trace_id`；
- 查看命中的画像规则；
- 查看审计记录；
- 查看待审阅任务。

### 11.2 审阅能力

工作台已支持：

- 确认；
- 驳回；
- 修改后确认；
- 查看是否允许导出或发送。

### 11.3 风险展示

高风险内容默认不展示为“可直接发送”状态。

建议展示：

|状态|UI 提示|
|---|---|
|`low`|内部参考|
|`medium + pending_review`|需律师确认|
|`high + pending_review`|高风险，禁止自动发送|
|`confirmed`|已确认，可导出/发送|
|`rejected`|已驳回，不可对外使用|

### 11.4 用户入口

MVP 工作台当前按单用户开发模式运行：

- 前端不再暴露 `user_id` / `session_id` 原始输入框；
- 界面展示“当前用户”与“切换用户”入口；
- 当前默认用户为 `web_user`，默认会话为 `web_session`；
- 多用户模块暂不实现登录、权限和用户列表，但代码中已将用户状态集中在 `state.activeUser`，后续可替换为登录态或用户选择弹窗。

### 11.5 MVP 核心指令

工作台当前预置 6 个轻量核心指令。指令由前端命令表集中管理，MVP 阶段用于快速操作页面状态；后续扩展指令列表时，应优先在命令表中新增，不把指令逻辑散落到按钮事件中。

|指令|用途|
|---|---|
|`/help`|提供帮助引导|
|`/clear`|清理当前页面缓存|
|`/new`|新建一次空白处理|
|`/review`|加载待审阅任务|
|`/examples`|查看输入示例|
|`/status`|查看服务与模型状态|

---

## 12. 云端部署规划

### 12.1 部署路线

推荐路线：

```text
MVP：ECS + Docker Compose + Nginx + HTTPS
低运维备选：SAE 镜像部署
企业级扩展：ACK / Kubernetes
```

### 12.2 云端组件

|组件|用途|
|---|---|
|ECS / SAE|运行 FastAPI 服务|
|Nginx / 网关|反向代理、HTTPS|
|RDS PostgreSQL|业务数据、画像、审计、审阅任务|
|OSS|知识库源文件、上传文件、导出文书归档|
|Redis / Tair|短期会话缓存、任务状态缓存|
|日志与监控|健康检查、指标、告警|

### 12.3 运维能力

需要补齐：

- 服务健康检查；
- 结构化日志；
- 监控指标；
- 异常告警；
- 数据备份；
- 恢复策略；
- 环境变量和密钥管理。

---

## 13. 安全与合规

### 13.1 基本原则

- 脱敏优先；
- 最小权限；
- 人工确认；
- 全链路审计；
- 高风险默认拦截；
- 对外动作显式记录。

### 13.2 必须人工确认的环节

```text
1. 画像规则入库
2. 旧规则修正
3. 反例边界建立
4. 对外法律意见输出
5. 敏感信息处理
6. 客户可见内容生成
7. 系统权限变更
```

### 13.3 当前已实现的合规能力

- 处理请求写入审计；
- 输入摘要和输出摘要分开记录；
- 画像规则使用记录进入 `tools_used`；
- 中高风险自动创建审阅任务；
- 确认/驳回同步审计标记；
- 导出/发送动作独立写入审计明细；
- 已驳回内容禁止导出或发送。

### 13.4 待补齐的合规能力

- 登录与身份认证；
- 角色权限控制；
- API 鉴权；
- 敏感词与敏感字段拦截；
- 文件上传安全；
- 云端密钥管理；
- 审计日志不可篡改策略。

---

## 14. 当前已完成与待完成

### 14.1 已完成

- `LawOrchestrator` 作为法律业务核心；
- `RiskLabeler` 作为风险门禁；
- `AuditLogger` 作为合规留痕；
- `ClientProfileStore` 作为客户画像记忆库；
- `/process` 标准响应扩展；
- 画像导入与查询 API；
- 审计查询 API；
- 画像驱动编排；
- 中高风险人工审阅任务；
- 审阅确认 / 驳回 API；
- 导出 / 发送 API；
- 导出 / 发送审计明细。
- Web 工作台 MVP；
- 审阅任务列表 API。
- OpenAI 兼容模式 LLM 客户端；
- LLM 增强文书生成，失败时自动退回模板。

### 14.2 下一步

优先级建议：

1. OpenClaw Skill 层；
2. Gateway 接入；
3. 定时画像周更；
4. ECS + Docker Compose 云端部署；
5. DashScope / 百炼 LLM 客户端；
6. 百炼知识库或 DashVector；
7. RDS PostgreSQL 迁移。

---

## 15. 版本路线图

### v0.2 当前基线

目标：

```text
完成 Law Agent 后端闭环。
```

状态：

- 已完成基础 API；
- 已完成画像 API；
- 已完成审计 API；
- 已完成风险与人工审阅闭环；
- 已完成导出/发送门禁。
- 已完成 OpenAI 兼容模式 LLM 接入。

### v0.3 Web 工作台

目标：

```text
让律师能在可视化界面查看结果、风险、画像、审计并完成审阅。
```

状态：

- 已完成 MVP；
- 已提供 `/workbench`；
- 已接入审阅任务列表；
- 已接入确认、驳回、修改后确认；
- 已将工作台用户入口调整为单用户按钮，并预留多用户切换模块；
- 已预置 `/help`、`/clear`、`/new`、`/review`、`/examples`、`/status` 六个核心指令；
- 已默认拦截未确认的中高风险导出/发送动作。

### v0.4 OpenClaw Skill 与 Gateway

目标：

```text
让 OpenClaw 只通过 FastAPI 调用 Law Agent。
```

重点：

- Skill 定义；
- Gateway 格式；
- 高风险展示策略；
- 人工审阅通知。

### v0.5 云端部署

目标：

```text
让 Law Agent 具备 7x24 在线运行能力。
```

重点：

- ECS / SAE；
- Nginx + HTTPS；
- 环境变量；
- 监控告警；
- 数据备份。

### v0.6 阿里云模型与知识库

目标：

```text
接入 DashScope / 百炼和可更新法律知识库。
```

重点：

- LLM 客户端；
- 知识库检索；
- 元数据 schema；
- OSS 文件归档；
- 知识更新流水线。

### v0.7 数据云端化

目标：

```text
将画像、审计、审阅任务迁移到 RDS PostgreSQL。
```

重点：

- 数据模型迁移；
- 兼容当前 SQLite 接口；
- 权限与审计增强；
- 备份恢复。

---

## 16. 三个核心判断

### 16.1 第一根钉子：法律核心不能外包给接入层

OpenClaw 可以接入消息、调度任务、通知律师，但不能接管法律判断。法律业务核心必须留在 Law Agent。

### 16.2 第二根钉子：画像和知识库不能混用

画像库解决“这个律师通常怎么处理”，知识库解决“法律依据在哪里”。混用会把经验策略误包装成客观法律结论。

### 16.3 第三根钉子：高风险输出必须有人工闭环

只要内容可能对外产生法律后果，就必须经过风险门禁、人工审阅和审计留痕。系统的价值不是自动替代律师，而是让律师判断更结构化、更可追踪、更可复盘。
