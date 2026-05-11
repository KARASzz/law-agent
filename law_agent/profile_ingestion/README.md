# 律师画像数据批处理工具

本目录是 Law Agent 系统内置的画像数据入库工作区。核心清洗逻辑在 `law_agent.profile_pipeline`，这里保留 Excel 输入、JSON 输出、配置、示例数据和说明文档。

原则：

> 只处理脱敏后的抽象行为逻辑和协作偏好，不保存原始案件细节。

默认不调用 LLM。

---

## 1. 支持的数据表

### 正式画像采集表

用于生成可导入正式画像库的 JSON。

- 用户填写版：`01_用户填写表`
- 开发清洗版：`01_极简采集表`

输出结构仍是：

- `source`
- `taxonomy`
- `judgment_model`
- `review_and_ingestion`
- `quality_control`

可直接导入 `data/client_profiles.db`。

### 助理每日协作记录表

用于生成“候选画像池”，不直接影响正式策略。

默认识别工作表：

```text
每日协作记录
```

只有 `是否适合沉淀为习惯` 以“是”开头的记录会进入候选池。候选规则由确定性模板生成，例如：

```text
在【案例检索】任务中，律师偏好【以后优先列法院观点+可引用句】；常用交付物为【法规/案例摘要】。
```

候选画像会同时：

- 输出到 `law_agent/profile_ingestion/output/*.json`
- 写入 `data/profile_candidates.db`

后续必须通过批处理人工选择后，才会升格进入正式画像库。

---

## 2. 文件夹结构

```text
law_agent/profile_ingestion/
├─ input/                  # 放 Excel 采集表
├─ output/                 # 输出清洗 JSON / 候选 JSON / 升格 JSON
├─ clean_to_json.py         # 旧命令兼容入口，转发到 law_agent.profile_pipeline
├─ config.json              # 批处理配置
├─ requirements.txt         # 兼容说明；主依赖看根目录 requirements.txt
└─ schemas/
   └─ output_schema_example.json
```

系统数据默认写到：

```text
data/client_profiles.db      # 正式画像库
data/profile_candidates.db   # 助理协作候选画像池
```

---

## 3. 第一次使用

在项目根目录安装依赖：

```bash
pip install -r requirements.txt
```

其中 `openpyxl` 已加入根目录依赖，用于读取 Excel。

---

## 4. 批处理菜单

双击：

```text
画像数据入库.bat
```

macOS 双击：

```text
画像数据入库.command
```

菜单能力：

| 选项 | 用途 |
|---|---|
| `[1] Clean user template` | 清洗用户版采集表，只输出 JSON |
| `[2] Clean developer template` | 清洗开发版采集表，只输出 JSON |
| `[3] Choose Excel file manually` | 手动选择正式画像采集表并清洗 |
| `[4] Clean chosen file and import to DB` | 清洗正式画像采集表并导入 `client_profiles.db` |
| `[5] Clean assistant table to candidate pool` | 清洗助理表并写入候选池 |
| `[6] Promote candidates to official profile DB` | 从候选池选择记录，升格入正式画像库 |
| `[7] Candidate pool stats` | 查看候选池统计 |
| `[8] Show latest output file` | 查看最新输出 JSON |
| `[9] Diagnostics` | 检查 Python、依赖和模块语法 |

不会在 Web 工作台出现入口。

---

## 5. CLI 命令

批处理内部调用这些命令，也可以手动运行。

清洗正式画像采集表：

```bash
python -m law_agent.profile_pipeline clean-profile \
  --input law_agent/profile_ingestion/input/律师客户画像_开发版_v4_含画像更新动作.xlsx \
  --output-dir law_agent/profile_ingestion/output \
  --config law_agent/profile_ingestion/config.json
```

清洗并导入正式画像库：

```bash
python -m law_agent.profile_pipeline clean-profile \
  --input law_agent/profile_ingestion/input/律师客户画像_开发版_v4_含画像更新动作.xlsx \
  --output-dir law_agent/profile_ingestion/output \
  --config law_agent/profile_ingestion/config.json \
  --import-db data/client_profiles.db
```

清洗助理协作表到候选池：

```bash
python -m law_agent.profile_pipeline clean-assistant \
  --input law_agent/profile_ingestion/input/律师助理每日协作记录表.xlsx \
  --output-dir law_agent/profile_ingestion/output \
  --config law_agent/profile_ingestion/config.json \
  --candidate-db data/profile_candidates.db
```

列出候选：

```bash
python -m law_agent.profile_pipeline list-candidates \
  --config law_agent/profile_ingestion/config.json \
  --candidate-db data/profile_candidates.db
```

升格指定候选：

```bash
python -m law_agent.profile_pipeline promote-candidates \
  --config law_agent/profile_ingestion/config.json \
  --candidate-db data/profile_candidates.db \
  --client-profile-db data/client_profiles.db \
  --candidate-ids cand_xxx,cand_yyy
```

---

## 6. 脱敏与质量规则

脚本会继续做基础脱敏扫描。

会自动替换：

- 身份证号
- 手机号
- 邮箱
- 疑似案号
- 疑似金额
- 疑似具体日期

会提示人工复核：

- 疑似具体司法/行政机构
- 疑似自然人姓名提示
- 异常超长文本

正式画像里，`privacy_decision != pass` 的记录不会被 `ClientProfileStore` 导入。
助理候选里，命中敏感风险的候选会保留在候选池，但不能通过默认升格流程进入正式画像库。

---

## 7. 重要边界

1. 正式采集表可以清洗并导入正式画像库。
2. 助理协作表先进入候选画像池，不直接影响 `LawOrchestrator`。
3. 候选升格必须通过批处理人工选择。
4. 默认不启用 LLM；`config.json` 中的 `model.use_model` 保持 `false`。
5. 不在 Web 工作台增加清洗、候选池或升格入口。
