# 律师客户画像采集表清洗入库脚本

## 1. 这个工具解决什么问题

把每周收集到的 Excel 采集表，清洗成可入库的 JSON 文件。

原则：

> 只输出抽象行为逻辑，不输出案件细节。

适合两种表：

- 客户填写版：`01_用户填写表`
- 开发清洗版：`01_极简采集表`

脚本会自动识别表头位置，兼容客户版和开发版。

---

## 2. 文件夹结构

```text
lawyer_profile_cleaner/
├─ input/                 # 每周把 Excel 采集表放这里
├─ output/                # 清洗后的 JSON 输出到这里
├─ clean_to_json.py        # 主清洗脚本
├─ run_clean.bat           # Windows 一键执行批处理
├─ config.json             # 配置文件
├─ requirements.txt        # Python 依赖
└─ schemas/
   └─ output_schema_example.json
```

---

## 3. 第一次使用

### 3.1 安装 Python

建议使用 Python 3.10+。

### 3.2 安装依赖

在根目录打开命令行：

```bash
pip install -r requirements.txt
```

---

## 4. 每周使用流程

### 第一步：放入 Excel

把本周收集到的 `.xlsx` 文件放到：

```text
input/
```

### 第二步：运行批处理

双击：

```text
run_clean.bat
```

如果 `run_clean.bat` 里没有指定文件名，它会自动列出 `input` 文件夹内的 Excel 文件，让你输入编号选择。

如果你想在批处理里手动固定文件名，打开 `run_clean.bat`，修改这一行：

```bat
set "INPUT_FILE="
```

例如：

```bat
set "INPUT_FILE=2026年第18周_客户画像采集.xlsx"
```

### 第三步：查看输出

清洗后的 JSON 会出现在：

```text
output/
```

文件名格式类似：

```text
2026年第18周_客户画像采集_cleaned_20260504_212300.json
```

---

## 5. 输出 JSON 包含哪些内容

每条记录会被整理成四块：

| JSON 区块 | 含义 |
|---|---|
| `source` | 来源文件、工作表、Excel 行号 |
| `taxonomy` | 案件类型、阶段、代表性等分类信息 |
| `judgment_model` | 画像建模最核心的抽象行为逻辑 |
| `review_and_ingestion` | 复盘标签、入库等级、画像更新动作等内部字段 |
| `quality_control` | 脱敏扫描、缺失字段、是否需要人工复核 |

核心字段在：

```json
"judgment_model": {
  "conflict_structure": "...",
  "key_constraints": "...",
  "first_judgment": "...",
  "abstract_reason": "...",
  "strategy_choice": "...",
  "value_order": "...",
  "risk_communication": "...",
  "handling_temperature": "...",
  "reusable_rule": "..."
}
```

---

## 6. 脱敏规则

脚本会做基础脱敏扫描和替换。

会自动替换：

- 身份证号
- 手机号
- 邮箱
- 疑似案号
- 疑似金额
- 疑似具体日期

会提示人工复核：

- 疑似具体法院/检察院/公安/仲裁机构名称
- 疑似自然人姓名占位信息
- 异常超长文本

注意：

> 脚本只做基础脱敏，不替代你的人工清洗判断。

如果输出里的：

```json
"privacy_decision": "needs_manual_review"
```

说明这一条建议你人工复核后再入库。

---

## 7. 字段缺失怎么处理

脚本会检查四个核心字段：

- `冲突结构`
- `第一判断`
- `策略选择`
- `可复用规则`

如果缺失，会写入：

```json
"missing_core_fields": []
```

如果核心字段缺得太多，会标记：

```json
"privacy_decision": "low_value_or_incomplete"
```

这类记录可以不入库，或补采后再入库。

---

## 8. 模型调用占位符

默认不调用模型。

如需接入模型，在 `config.json` 里设置：

```json
"model": {
  "use_model": true,
  "provider": "TODO: aliyun_or_other",
  "endpoint": "TODO: fill_your_model_endpoint_here",
  "api_key_env": "MODEL_API_KEY",
  "model_name": "TODO: fill_model_name_here"
}
```

然后在 `clean_to_json.py` 中补充：

```python
def normalize_with_model(record, model_config):
    # 在这里接入你的模型调用
    return record
```

建议模型只处理这些字段：

```text
conflict_structure
key_constraints
first_judgment
abstract_reason
strategy_choice
value_order
risk_communication
handling_temperature
reusable_rule
```

不要把任何原始案件材料、当事人信息、案号、金额、法院、人名发给模型。

---

## 9. 推荐入库规则

最小入库判断：

| 条件 | 动作 |
|---|---|
| `privacy_decision = pass` 且 `reusable_rule` 不为空 | 可入库 |
| `needs_manual_review` | 人工复核后再决定 |
| `low_value_or_incomplete` | 不入库或补采 |
| `profile_update_action = 强化旧规则` | 强化已有画像规则 |
| `profile_update_action = 修正旧规则` | 修改旧规则适用边界 |
| `profile_update_action = 建立反例边界` | 写入反例库 |
| `profile_update_action = 新增规则` | 新建画像规则 |
| `profile_update_action = 更新触发条件` | 补充策略转向条件 |

---

## 10. 重要边界

1. 这个脚本不保存原始整行数据。
2. 这个脚本不替你判断案件事实。
3. 这个脚本只做抽象行为逻辑清洗。
4. 这个脚本输出的 JSON 仍建议由你人工复核后再正式入库。
5. 客户版文件不要暴露开发版字段；开发版 JSON 不要原样交给客户。

---

## 11. 常见问题

### Q1：客户版少字段，脚本能读吗？

能。脚本兼容客户版和开发版。客户版没有的字段会输出为空。

### Q2：开发版的复盘标签和画像更新动作会输出吗？

会。如果输入是开发版，脚本会读取并输出到 `review_and_ingestion`。

### Q3：客户版里没有复盘标签，怎么办？

正常。复盘标签、画像更新动作由你在开发版清洗阶段填写，不要求客户填。

### Q4：可以一次处理多个文件吗？

当前批处理默认一次处理一个文件。后续可以扩展为批量模式。

### Q5：输出能直接喂给阿里云记忆库吗？

建议先人工复核，再根据阿里云记忆库的接口要求做字段映射。这个版本先输出通用 JSON，便于你二次加工。
