# 合并画像数据清洗工具到系统

## Summary

将原独立前置工具整理为系统内的“画像数据批处理管线”，工作区并入 `law_agent/profile_ingestion`，入口放在项目根目录的 `画像数据入库.bat` / `画像数据入库.command`，不在 Web 工作台增加任何入口。
正式采集表继续清洗成现有客户画像 JSON 并可导入 `data/client_profiles.db`；助理每日协作表进入“候选画像池”，同时输出 JSON 归档和写入 SQLite，后续通过批处理人工选择后再升格入正式画像库。默认不启用 LLM。

## Key Changes

- 新增系统内画像清洗模块，例如 `law_agent.profile_pipeline`：
  - `clean_profile_workbook(...)`：承接现有开发版/用户版采集表清洗逻辑。
  - `clean_assistant_workbook_to_candidates(...)`：把“每日协作记录”转为候选画像。
  - `promote_candidates(...)`：批处理选择候选记录，生成正式画像 JSON，并调用现有 `ClientProfileStore.ingest_json_file()` 导入。
- 保留 `law_agent/profile_ingestion/clean_to_json.py` 作为兼容入口或薄封装，核心逻辑迁入系统模块，避免两套清洗代码分叉。
- 根目录启动器菜单：
  - 清洗用户版/开发版采集表。
  - 清洗并导入正式画像库。
  - 清洗助理协作表到候选画像池。
  - 从候选池选择记录并升格入正式画像库。
  - 查看最新输出、候选池统计、诊断依赖。
- 不修改 `law_agent/static/workbench.html`，不增加工作台按钮、上传入口或候选池页面；现有 API 可保持不变，但新增候选池能力只通过批处理/CLI 使用。

## Candidate Pool

- 新增候选池 SQLite，例如 `data/profile_candidates.db`：
  - `profile_candidate_batches`：记录来源文件、hash、输出 JSON、统计信息、生成时间。
  - `profile_candidates`：记录候选 ID、来源行、助理表字段、候选规则、质量检查、复核状态、升格状态。
- 助理表识别规则：
  - 工作表优先匹配 `每日协作记录`。
  - 表头包含 `日期`、`助理姓名`、`服务律师`、`工作类型`、`律师反馈或修改方向`、`是否适合沉淀为习惯`。
- 候选生成规则：
  - 只有 `是否适合沉淀为习惯` 包含“是”的记录默认进入候选池。
  - `律师反馈或修改方向` 是核心字段；为空则标记为低价值候选，不升格。
  - 候选规则用确定性模板生成，例如：在【工作类型】任务中，律师偏好【律师反馈或修改方向】；常用交付物为【交付物类型】。
  - 继续复用现有脱敏扫描；命中敏感风险的候选保留但标记 `needs_manual_review`，不得自动升格。
- 升格到正式画像时，映射到现有画像 JSON：
  - `data_source = 助理协作记录`
  - `role_pattern = 律师-助理协作`
  - `first_judgment = 可沉淀协作习惯`
  - `strategy_choice = 律师反馈或修改方向`
  - `reusable_rule = 候选规则`
  - `ingestion_level = B可用样本`
  - `review_tag = 协作偏好`
  - `profile_update_action = 新增规则`

## Interfaces And Config

- 扩展 `law_agent/profile_ingestion/config.json`：
  - `candidate_db_path`: `../../data/profile_candidates.db`
  - `client_profile_db_path`: `../../data/client_profiles.db`
  - `assistant_candidates.sheet_candidates`: `["每日协作记录"]`
  - `assistant_candidates.include_uncertain`: `false`
  - `assistant_candidates.default_ingestion_level`: `"B可用样本"`
  - `model.use_model`: 保持 `false`
- 根目录 `requirements.txt` 增加 `openpyxl>=3.1.2`，确保主系统环境可直接跑批处理。
- 批处理内部调用 Python 模块，例如：
  - `python -m law_agent.profile_pipeline clean-profile ...`
  - `python -m law_agent.profile_pipeline clean-assistant ...`
  - `python -m law_agent.profile_pipeline promote-candidates ...`

## Test Plan

- 新增正式采集表清洗测试：开发版/用户版输入仍生成现有 schema，且可被 `ClientProfileStore` 导入。
- 新增助理表候选测试：示例两行协作记录生成两个候选，字段映射、候选规则、统计数量正确。
- 新增隐私测试：手机号、案号、金额、具体日期等仍会脱敏或标记复核。
- 新增升格测试：只有批处理中选中的候选会生成正式画像 JSON 并导入 `lawyer_client_profiles`；未选中候选不会影响正式策略。
- 新增工作台保护测试：不修改工作台 HTML，不出现候选池、清洗、导入相关入口文案。
- 回归测试：运行现有 `tests/test_client_profiles.py`、`tests/test_api_contract.py`，确认画像库和 API 行为不被破坏。

## Assumptions

- 助理表默认不使用 LLM；候选规则由确定性模板生成。
- 助理协作记录先进入候选池，不直接参与 `LawOrchestrator` 策略匹配。
- 候选升格必须通过批处理人工选择完成。
- 正式画像库继续沿用当前 SQLite 结构，暂不引入工作台复核页面。
