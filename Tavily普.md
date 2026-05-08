# Tavily 用法详细攻略

结论先放前面：**Tavily 不是普通搜索 API，而是一套给 AI Agent / RAG / 深度研究系统接入实时网页信息的工具组**。核心能力可以压成这张图：

```text
Tavily
│
├─ Search：不知道具体网址，先找信息源
├─ Extract：已经有网址，提取网页正文
├─ Map：只想发现一个网站下有哪些 URL
├─ Crawl：想沿着网站结构抓取多页内容
├─ Research：让 Tavily 自动多轮搜索、分析、生成带来源的研究结果
├─ Usage：查用量、额度、消耗
│
├─ Python / JS SDK：程序内调用
├─ CLI：命令行调用
├─ MCP Server：接入 Claude、Cursor、OpenAI Agents 等工具生态
├─ Agent Skills：给 ChatGPT / Claude / Gemini 等智能体装“搜索技能包”
└─ Hybrid RAG：把实时网页信息和你自己的向量库 / 数据库合并检索
```

我按官方文档索引覆盖了 API、SDK、CLI、MCP、Agent Skills、Hybrid RAG、Best Practices 和 Use Cases，不逐页复读，而是整理成可执行攻略。官方文档索引本身列出了 Search、Extract、Crawl、Map、Research、Usage、CLI、MCP、SDK、Agent Skills、Integrations、Examples 等模块。([docs.tavily.com][1])
整理方式按你项目里的“查证、拆解、落地、钉住”思路处理，避免只做文档搬运。

---

## 0. 快速开始：最小可运行版本

Tavily 官方 Quickstart 的最短路径是：创建 API Key，安装 SDK，然后调用 `search()`。文档目前写明新账户每月有 1,000 free credits，且不需要信用卡；这个额度以后可能变，实际以控制台为准。([docs.tavily.com][2])

### Python 安装

```bash
pip install tavily-python
```

### 第一次搜索

```python
from tavily import TavilyClient

client = TavilyClient(api_key="tvly-YOUR_API_KEY")

response = client.search("What happened in the latest AI regulation news?")

print(response)
```

### 推荐的环境变量写法

```bash
export TAVILY_API_KEY="tvly-YOUR_API_KEY"
```

```python
import os
from tavily import TavilyClient

client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])

result = client.search(
    query="latest AI agent framework updates",
    max_results=5,
)

print(result["results"])
```

---

# 1. 功能选择表：什么时候用哪个？

| 目标                 |                用哪个功能 | 返回什么                | 适合场景                                   |
| ------------------ | -------------------: | ------------------- | -------------------------------------- |
| 我不知道网址，只知道问题       |             `Search` | 相关网页、标题、摘要、URL、可选答案 | 新闻、事实查询、竞品监控、Agent 搜索                  |
| 我已经有 URL，想读正文      |            `Extract` | 网页正文、图片、失败列表        | 把搜索结果变成可喂给模型的干净文本                      |
| 我想知道一个网站有哪些页面      |                `Map` | URL 列表              | 文档站、官网、博客、产品页发现                        |
| 我想抓一个网站的多页内容       |              `Crawl` | 多个页面的正文内容           | 构建知识库、RAG 数据采集、文档同步                    |
| 我想让 Tavily 自动做深度研究 |           `Research` | 研究报告、来源、结构化结果       | 市场调研、政策研究、竞品分析                         |
| 我想查消耗              |              `Usage` | 账户 / 项目使用量          | 成本控制、项目计费、监控                           |
| 我想在终端里用            |                `CLI` | 命令行输出 / JSON        | 测试、脚本、自动化                              |
| 我想接入智能体工具          | `MCP / Agent Skills` | 工具调用能力              | Claude、Cursor、OpenAI Agents、ChatGPT 项目 |
| 我想同时查本地库和网页        |         `Hybrid RAG` | 本地 + Web 混合结果       | 企业知识库 + 实时信息补全                         |

---

# 2. Search：搜索网页信息

## 2.1 作用

`Search` 是 Tavily 最核心的入口：输入一个 query，返回相关网页结果，并可选返回答案、图片、原始正文、favicon、usage 等字段。官方 Search API 支持 `query`、`search_depth`、`topic`、时间范围、域名过滤、国家过滤、图片、答案、原文、usage 等参数。([docs.tavily.com][3])

## 2.2 最小示例

```python
from tavily import TavilyClient

client = TavilyClient(api_key="tvly-YOUR_API_KEY")

result = client.search(
    query="latest OpenAI API updates",
    max_results=5,
)

for item in result["results"]:
    print(item["title"])
    print(item["url"])
    print(item["content"])
    print()
```

## 2.3 搜索深度：`search_depth`

官方文档把搜索深度分为多档：`basic`、`advanced`、`fast`、`ultra_fast`。`advanced` 会更深入，但消耗更多 credits；文档也说明 `advanced` 搜索通常消耗 2 credits，而 `basic`、`fast`、`ultra_fast` 消耗更少。([docs.tavily.com][3])

```python
result = client.search(
    query="AI safety regulation European Union 2026",
    search_depth="advanced",
    max_results=10,
)
```

### 怎么选？

| 参数           | 适合              |
| ------------ | --------------- |
| `basic`      | 普通事实查询、快速找几个来源  |
| `advanced`   | 需要更全、更深、更可信的结果  |
| `fast`       | 低延迟应用，比如聊天机器人   |
| `ultra_fast` | 对速度极敏感，允许牺牲部分深度 |

---

## 2.4 搜索新闻 / 时间范围

`topic` 可以选择 `general` 或 `news`。时间过滤支持 `time_range`、`days`、`start_date`、`end_date` 等，用来控制结果的新旧。([docs.tavily.com][3])

```python
result = client.search(
    query="semiconductor export controls Japan United States",
    topic="news",
    time_range="week",
    max_results=8,
    include_answer="basic",
)

print(result["answer"])
```

### 常用时间参数

```python
# 最近一天
client.search(query="AI model release news", time_range="day")

# 最近一周
client.search(query="sports technology investment", time_range="week")

# 最近一个月
client.search(query="anti-doping policy updates", time_range="month")

# 指定日期区间
client.search(
    query="World Athletics anti-doping rule changes",
    start_date="2026-01-01",
    end_date="2026-05-01",
)
```

---

## 2.5 域名过滤：只搜指定网站

Search 支持 `include_domains` 和 `exclude_domains`。官方最佳实践建议：当你知道高质量来源时，用 `include_domains`；当某些来源噪声大时，用 `exclude_domains`。([docs.tavily.com][4])

```python
result = client.search(
    query="anti-doping testing protocol 2026",
    include_domains=[
        "wada-ama.org",
        "worldathletics.org",
    ],
    search_depth="advanced",
    max_results=5,
)
```

### 排除低质量来源

```python
result = client.search(
    query="best AI coding assistants 2026",
    exclude_domains=[
        "reddit.com",
        "quora.com",
    ],
    max_results=10,
)
```

---

## 2.6 精确匹配：`exact_match`

`exact_match=True` 会要求结果包含用户 query 中的重要词或短语。官方文档建议它适合查公司名、产品名、精确短语，但也提醒结果可能变少。([docs.tavily.com][4])

```python
result = client.search(
    query='"Tavily MCP Server"',
    exact_match=True,
    max_results=5,
)
```

---

## 2.7 返回答案、正文、图片

```python
result = client.search(
    query="What is Tavily Research API?",
    include_answer="advanced",
    include_raw_content="markdown",
    include_images=True,
    include_image_descriptions=True,
    include_favicon=True,
    max_results=5,
)

print("Answer:", result["answer"])

for r in result["results"]:
    print(r["title"], r["url"])
    print(r.get("raw_content", "")[:500])
```

注意：`include_raw_content` 会让 Search 返回更多正文内容，但如果你要完整读网页，通常更稳的是 **Search → Extract**。官方最佳实践也建议，用 Search 找页面，再用 Extract 获取完整内容。([docs.tavily.com][4])

---

## 2.8 Search 的推荐工作流

```text
用户问题
  ↓
Search 找候选网页
  ↓
按 score / domain / date 过滤
  ↓
Extract 读取关键页面全文
  ↓
交给 LLM 总结 / 引用 / 推理
```

```python
search = client.search(
    query="Tavily Search API best practices",
    include_domains=["docs.tavily.com"],
    max_results=5,
)

urls = [item["url"] for item in search["results"]]

pages = client.extract(
    urls=urls,
    extract_depth="advanced",
    format="markdown",
)

for page in pages["results"]:
    print(page["url"])
    print(page["raw_content"][:1000])
```

---

# 3. Extract：提取网页正文

## 3.1 作用

`Extract` 用于从一个或多个 URL 中提取网页内容。它适合在你已经知道 URL 后，把网页转换为可用于 LLM、RAG 或总结的干净文本。官方 Extract API 支持单 URL / 多 URL、query 聚焦提取、chunks、提取深度、图片、favicon、markdown/text 格式和 usage。([docs.tavily.com][5])

## 3.2 最小示例

```python
result = client.extract(
    urls="https://docs.tavily.com/documentation/api-reference/endpoint/search"
)

print(result["results"][0]["raw_content"][:1000])
```

## 3.3 批量提取

```python
result = client.extract(
    urls=[
        "https://docs.tavily.com/documentation/api-reference/endpoint/search",
        "https://docs.tavily.com/documentation/api-reference/endpoint/extract",
    ],
    format="markdown",
)

for page in result["results"]:
    print(page["url"])
    print(page["raw_content"][:500])
```

## 3.4 按 query 聚焦提取

Extract 支持 `query` 和 `chunks_per_source`，可以让它只返回和问题相关的片段，而不是整页都读。([docs.tavily.com][5])

```python
result = client.extract(
    urls=[
        "https://docs.tavily.com/documentation/api-reference/endpoint/search"
    ],
    query="search_depth include_answer include_domains",
    chunks_per_source=5,
    format="markdown",
)

print(result["results"][0]["raw_content"])
```

## 3.5 深度提取

`extract_depth` 可选 `basic` 或 `advanced`。官方文档说明 `advanced` 更适合复杂网页或信息丰富的网站，但消耗更高；`basic` 成功提取每 5 个 URL 消耗 1 credit，`advanced` 成功提取每 5 个 URL 消耗 2 credits。([docs.tavily.com][5])

```python
result = client.extract(
    urls=[
        "https://example.com/long-technical-report"
    ],
    extract_depth="advanced",
    format="markdown",
    include_images=True,
    include_favicon=True,
    include_usage=True,
)
```

## 3.6 失败处理

Extract 返回里有 `results` 和 `failed_results`。要做生产系统，必须处理失败 URL。([docs.tavily.com][5])

```python
result = client.extract(
    urls=[
        "https://example.com/page-a",
        "https://example.com/page-b",
    ],
    timeout=30,
    include_usage=True,
)

for ok in result["results"]:
    print("OK:", ok["url"])

for failed in result["failed_results"]:
    print("FAILED:", failed["url"], failed.get("error"))
```

---

# 4. Map：发现网站 URL

## 4.1 作用

`Map` 不负责提取正文，主要负责发现一个网站下的 URL 列表。官方文档说 Map 会根据网站结构遍历页面，返回 URL 列表，可通过深度、广度、limit、路径过滤、外链控制等参数约束范围。([docs.tavily.com][6])

## 4.2 最小示例

```python
urls = client.map(
    url="https://docs.tavily.com",
    max_depth=2,
    limit=50,
)

for url in urls["results"]:
    print(url)
```

## 4.3 只发现文档页面

```python
urls = client.map(
    url="https://docs.tavily.com",
    max_depth=3,
    max_breadth=20,
    limit=200,
    select_paths=[
        "/documentation/.*",
        "/examples/.*",
    ],
    exclude_paths=[
        "/changelog/.*",
    ],
    allow_external=False,
    include_usage=True,
)

print(len(urls["results"]))
```

## 4.4 用自然语言 instructions 控制 Map

Map 支持 `instructions`，但官方文档提醒：使用 instructions 时，mapping 成本会提高。([docs.tavily.com][6])

```python
urls = client.map(
    url="https://docs.tavily.com",
    instructions="Find pages related to API reference, SDKs, CLI, MCP, and examples.",
    max_depth=3,
    limit=100,
)
```

## 4.5 Map 的典型组合

```text
Map 找 URL
  ↓
人工 / 程序筛选 URL
  ↓
Extract 批量提取正文
  ↓
写入知识库
```

```python
mapped = client.map(
    url="https://docs.tavily.com",
    select_paths=["/documentation/.*"],
    max_depth=3,
    limit=100,
)

pages = client.extract(
    urls=mapped["results"][:20],
    extract_depth="advanced",
    format="markdown",
)

for page in pages["results"]:
    print(page["url"], len(page["raw_content"]))
```

---

# 5. Crawl：抓取网站多页内容

## 5.1 作用

`Crawl` = Map + Extract 的更直接版本。它会沿着网站链接结构抓取多个页面，并返回每个页面的内容。官方文档称它是 graph-based traversal，支持 URL、instructions、深度、广度、limit、路径过滤、域名过滤、外链控制、提取深度、格式等参数。([docs.tavily.com][7])

## 5.2 最小示例

```python
result = client.crawl(
    url="https://docs.tavily.com",
    max_depth=1,
    limit=10,
)

for page in result["results"]:
    print(page["url"])
    print(page["raw_content"][:300])
```

## 5.3 抓文档站

```python
result = client.crawl(
    url="https://docs.tavily.com",
    instructions="Crawl documentation pages about API usage and SDK examples.",
    max_depth=3,
    max_breadth=20,
    limit=100,
    select_paths=[
        "/documentation/.*",
        "/examples/.*",
    ],
    exclude_paths=[
        "/changelog/.*",
    ],
    extract_depth="advanced",
    format="markdown",
    include_images=False,
    include_favicon=True,
    include_usage=True,
)
```

## 5.4 抓取时限制域名

```python
result = client.crawl(
    url="https://docs.tavily.com",
    select_domains=["docs.tavily.com"],
    allow_external=False,
    max_depth=2,
    limit=50,
)
```

## 5.5 Crawl 的成本刹车

Crawl 很容易烧 credits。官方文档里，`instructions` 会让 mapping 成本提高；同时 Crawl 中的内容提取还会根据 `extract_depth` 计费。([docs.tavily.com][7])

生产环境建议：

```python
result = client.crawl(
    url="https://target-site.com",
    max_depth=2,
    max_breadth=10,
    limit=50,
    extract_depth="basic",
    include_usage=True,
)
```

---

# 6. Research：自动深度研究

## 6.1 作用

`Research` 是 Tavily 的高级能力：输入一个研究问题，它会自动进行多次搜索、分析来源，并生成研究结果。官方文档说明 Research API 会执行 comprehensive research、分析多个来源，并生成 detailed report；它支持不同模型、流式输出、结构化输出 schema、引用格式等。([docs.tavily.com][8])

## 6.2 非流式研究

```python
result = client.research(
    input="Compare Tavily, Brave Search API, and Exa for AI agent web search use cases.",
    model="pro",
    citation_format="numbered",
)

print(result)
```

## 6.3 结构化输出

Research 支持 `output_schema`。你可以要求 Tavily 按固定 JSON 结构返回。([docs.tavily.com][8])

```python
schema = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "key_findings": {
            "type": "array",
            "items": {"type": "string"}
        },
        "comparison_table": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "tool": {"type": "string"},
                    "strength": {"type": "string"},
                    "weakness": {"type": "string"},
                    "best_use_case": {"type": "string"}
                },
                "required": ["tool", "strength", "weakness", "best_use_case"]
            }
        }
    },
    "required": ["summary", "key_findings", "comparison_table"]
}

result = client.research(
    input="Compare Tavily, Brave Search API, and Exa for AI agent search.",
    model="pro",
    output_schema=schema,
    citation_format="numbered",
)

print(result)
```

## 6.4 异步轮询

Research 可能返回 `request_id` 和 `status=pending`，然后通过 Get Research 接口轮询结果。官方 Get Research 文档说明可以根据 `request_id` 查询研究状态，状态包括 completed / failed 等。([docs.tavily.com][9])

```python
task = client.research(
    input="Research the latest anti-doping technology trends.",
    model="pro",
)

request_id = task["request_id"]

final = client.get_research(request_id=request_id)

print(final["status"])
print(final.get("content"))
```

## 6.5 流式研究

Research 支持 `stream=True`，流式事件包括 tool call、tool response、content、sources、done、error 等。官方文档给出了 SSE 事件结构和 Python / JS 示例。([docs.tavily.com][10])

```python
stream = client.research(
    input="Research current AI coding agent frameworks and compare their use cases.",
    model="pro",
    stream=True,
)

for event in stream:
    event_type = event.get("type")

    if event_type == "content":
        print(event.get("content"), end="")
    elif event_type == "sources":
        print("\n\nSources:", event.get("sources"))
    elif event_type == "done":
        print("\n\nDone")
```

## 6.6 Research 适合什么？

| 场景          |             是否适合 |
| ----------- | ---------------: |
| 一句话事实查询     |    不适合，Search 足够 |
| 多来源比较       |               适合 |
| 行业研究        |               适合 |
| 政策 / 法规现状梳理 | 适合，但关键结论仍要人工核验原文 |
| 写完整研究报告     |    适合做初稿，不应直接当终稿 |
| Agent 自主调研  |               适合 |

---

# 7. Usage：查询用量和成本

## 7.1 作用

Usage API 用于查询账户或项目的 API 使用量。官方 Usage 文档提供了 cURL 示例，并说明响应会包含 key / account usage，以及 Search、Extract、Crawl、Map、Research 等类别的消耗信息。([docs.tavily.com][11])

## 7.2 cURL 示例

```bash
curl -X GET "https://api.tavily.com/usage" \
  -H "Authorization: Bearer tvly-YOUR_API_KEY"
```

## 7.3 带项目 ID

```bash
curl -X GET "https://api.tavily.com/usage" \
  -H "Authorization: Bearer tvly-YOUR_API_KEY" \
  -H "X-Project-ID: YOUR_PROJECT_ID"
```

## 7.4 成本监控建议

```text
每次请求加 include_usage=True
  ↓
写入日志
  ↓
按功能统计 Search / Extract / Crawl / Research 消耗
  ↓
超阈值报警
```

```python
result = client.search(
    query="latest AI search APIs",
    include_usage=True,
)

print(result.get("usage"))
```

---

# 8. Python SDK：同步、异步、项目、代理

## 8.1 SDK 作用

官方 Python SDK 支持 Search、Extract、Crawl、Map 等 Tavily 功能，并提供同步 / 异步客户端、项目跟踪和代理设置。([docs.tavily.com][12])

## 8.2 同步客户端

```python
from tavily import TavilyClient

client = TavilyClient(api_key="tvly-YOUR_API_KEY")

result = client.search("Tavily Python SDK examples")

print(result)
```

## 8.3 异步客户端

```python
import asyncio
from tavily import AsyncTavilyClient

async def main():
    client = AsyncTavilyClient(api_key="tvly-YOUR_API_KEY")
    result = await client.search(
        query="latest AI agent search tools",
        max_results=5,
    )
    print(result)

asyncio.run(main())
```

官方最佳实践建议，在需要多个并发请求时使用异步方式，而不是串行等待。([docs.tavily.com][4])

## 8.4 项目追踪

```python
from tavily import TavilyClient

client = TavilyClient(
    api_key="tvly-YOUR_API_KEY",
    project_id="your-project-id",
)

result = client.search("AI governance tools")
```

## 8.5 代理配置

```python
client = TavilyClient(
    api_key="tvly-YOUR_API_KEY",
    proxies={
        "http": "http://127.0.0.1:7890",
        "https": "http://127.0.0.1:7890",
    },
)
```

---

# 9. JavaScript SDK：Node.js 调用

官方文档也提供 JS SDK 和 Research streaming 示例。Research Streaming 文档给了 JS 流式调用模式。([docs.tavily.com][10])

## 9.1 安装

```bash
npm install @tavily/core
```

## 9.2 Search 示例

```javascript
import { tavily } from "@tavily/core";

const tvly = tavily({
  apiKey: "tvly-YOUR_API_KEY",
});

const result = await tvly.search("latest AI agent frameworks", {
  maxResults: 5,
  searchDepth: "advanced",
});

console.log(result.results);
```

## 9.3 Research streaming 示例

```javascript
import { tavily } from "@tavily/core";

const tvly = tavily({
  apiKey: "tvly-YOUR_API_KEY",
});

const stream = await tvly.research({
  input: "Compare AI search APIs for agent systems.",
  model: "pro",
  stream: true,
});

for await (const event of stream) {
  if (event.type === "content") {
    process.stdout.write(event.content);
  }

  if (event.type === "sources") {
    console.log("\nSources:", event.sources);
  }
}
```

---

# 10. CLI：命令行用法

## 10.1 作用

Tavily CLI 可以直接在终端里运行 `search`、`extract`、`crawl`、`map`、`research`，并支持 `--json` 输出，适合测试、脚本和自动化。官方 CLI 文档列出了安装、认证、search/extract/crawl/map/research 命令、交互模式、JSON 输出和错误码。([docs.tavily.com][13])

## 10.2 安装

```bash
pip install tavily-cli
```

## 10.3 登录 / 设置 API Key

```bash
tavily auth
```

或者：

```bash
export TAVILY_API_KEY="tvly-YOUR_API_KEY"
```

## 10.4 Search

```bash
tavily search "latest AI coding agent frameworks" --max-results 5
```

```bash
tavily search "World Athletics anti-doping updates" \
  --topic news \
  --time-range month \
  --json
```

## 10.5 Extract

```bash
tavily extract "https://docs.tavily.com/documentation/api-reference/endpoint/search"
```

```bash
tavily extract \
  "https://docs.tavily.com/documentation/api-reference/endpoint/search" \
  --format markdown \
  --extract-depth advanced \
  --json
```

## 10.6 Crawl

```bash
tavily crawl "https://docs.tavily.com" \
  --max-depth 2 \
  --limit 20 \
  --format markdown
```

## 10.7 Map

```bash
tavily map "https://docs.tavily.com" \
  --max-depth 3 \
  --limit 100 \
  --json
```

## 10.8 Research

```bash
tavily research "Compare Tavily and Brave Search API for AI agents."
```

```bash
tavily research "Research latest AI web search APIs." \
  --model pro \
  --json
```

---

# 11. MCP Server：接入智能体工具生态

## 11.1 作用

MCP Server 让 Tavily 能作为工具接入支持 MCP 的客户端，比如 Claude Code、Cursor、OpenAI Agents 等。官方 MCP 文档提供了 remote MCP URL、本地安装、客户端配置、默认参数、自定义参数和排错说明。([docs.tavily.com][14])

## 11.2 Remote MCP 配置思路

Remote MCP URL 形态类似：

```text
https://mcp.tavily.com/mcp/?tavilyApiKey=tvly-YOUR_API_KEY
```

### Cursor 示例配置

```json
{
  "mcpServers": {
    "tavily": {
      "url": "https://mcp.tavily.com/mcp/?tavilyApiKey=tvly-YOUR_API_KEY"
    }
  }
}
```

## 11.3 OpenAI Agents SDK 调用思路

官方 MCP 文档提供了用 OpenAI Agents SDK 接入 remote MCP server 的示例。([docs.tavily.com][14])

```python
from agents import Agent, Runner
from agents.mcp import MCPServerStreamableHttp

async with MCPServerStreamableHttp(
    params={
        "url": "https://mcp.tavily.com/mcp/?tavilyApiKey=tvly-YOUR_API_KEY"
    }
) as tavily_mcp:
    agent = Agent(
        name="Research Agent",
        instructions="Use Tavily to search the web and extract relevant information.",
        mcp_servers=[tavily_mcp],
    )

    result = await Runner.run(
        agent,
        "Find recent updates about AI search APIs."
    )

    print(result.final_output)
```

## 11.4 默认参数

MCP 文档说明可以设置默认搜索参数，例如 `search_depth`、`topic`、`max_results` 等。([docs.tavily.com][14])

```json
{
  "mcpServers": {
    "tavily": {
      "url": "https://mcp.tavily.com/mcp/?tavilyApiKey=tvly-YOUR_API_KEY",
      "defaultParameters": {
        "search_depth": "advanced",
        "max_results": 5,
        "topic": "general"
      }
    }
  }
}
```

---

# 12. Agent Skills：给模型装 Tavily 技能

## 12.1 作用

Tavily Agent Skills 是官方提供的一组可安装技能，用于让 ChatGPT、Claude、Gemini 等智能体调用 Tavily 的搜索、提取、站点地图、抓取、研究等能力。官方文档列出了 search、extract、map、crawl、research 这些技能，并提供 slash command 使用方式。([docs.tavily.com][15])

## 12.2 安装思路

文档中的技能包按不同平台分发。你可以把它理解成：

```text
下载 / 安装 Tavily Skills
  ↓
填入 Tavily API Key
  ↓
在智能体中使用 /tavily-search、/tavily-extract 等命令
```

## 12.3 Skill 使用示例

### Search Skill

```text
/tavily-search latest AI agent frameworks 2026
```

### Extract Skill

```text
/tavily-extract https://docs.tavily.com/documentation/api-reference/endpoint/search
```

### Map Skill

```text
/tavily-map https://docs.tavily.com
```

### Crawl Skill

```text
/tavily-crawl https://docs.tavily.com
```

### Research Skill

```text
/tavily-research Compare Tavily, Brave Search API, and Exa for AI agent search.
```

## 12.4 适合什么？

| 场景                   |               是否适合 |
| -------------------- | -----------------: |
| 你想让 ChatGPT 项目具备搜索工具 |                 适合 |
| 你想让 Claude Code 查文档  |                 适合 |
| 你想做智能体原型             |                 适合 |
| 你要严格管控成本、权限、日志       | 建议用 MCP / SDK 自己封装 |

---

# 13. Hybrid RAG：实时 Web + 本地知识库

## 13.1 作用

Tavily Hybrid RAG 用于把 Tavily 的实时 Web 搜索和你自己的数据库 / 向量库结合。官方文档说明，Hybrid RAG 可以同时查 Web 和已有数据库，也可以把 Web 数据保存到数据库中。([docs.tavily.com][16])

## 13.2 典型场景

```text
用户问题
  ↓
先查本地知识库
  ↓
如果本地信息过时 / 不足
  ↓
用 Tavily 查实时 Web
  ↓
合并排序
  ↓
生成带来源答案
  ↓
可选：把新网页内容写回知识库
```

## 13.3 MongoDB 示例思路

官方示例使用 MongoDB，并默认配合 Cohere 生成 embedding。([docs.tavily.com][16])

```python
from tavily import TavilyHybridClient

hybrid_client = TavilyHybridClient(
    api_key="tvly-YOUR_API_KEY",
    db_provider="mongodb",
    collection=your_mongo_collection,
)

result = hybrid_client.search(
    query="latest Tavily MCP Server usage",
    max_results=5,
    max_local=3,
    save_to_db=True,
)

print(result)
```

## 13.4 适合你的几个方向

| 你的项目    | Tavily Hybrid RAG 用法                  |
| ------- | ------------------------------------- |
| AI研究室   | 实时查官方文档 + 本地方法论库                      |
| 体育智能系统  | 查规则 / 新闻 / 政策变动 + 本地运动员数据，不要混淆权限      |
| 反兴奋剂知识库 | 官方 WADA / World Athletics 动态 + 本地制度文件 |
| 提示词工厂   | 查模型 / SDK / API 最新文档 + 本地提示词资产        |
| 小说资料库   | 查科技资料、地理、历史、军事细节 + 本地设定集              |

---

# 14. 最推荐的 6 套实战组合

## 14.1 实时问答 Agent

```text
用户问题
  ↓
Tavily Search
  ↓
LLM 生成答案
  ↓
引用 URL
```

```python
def web_answer(question: str):
    result = client.search(
        query=question,
        search_depth="advanced",
        include_answer="advanced",
        max_results=5,
    )

    return {
        "answer": result.get("answer"),
        "sources": [
            {"title": r["title"], "url": r["url"]}
            for r in result["results"]
        ],
    }
```

---

## 14.2 可追溯研究助手

```text
Search 找来源
  ↓
Extract 读全文
  ↓
模型总结
  ↓
保留 URL 与引用
```

```python
def sourced_research(query: str):
    search = client.search(
        query=query,
        search_depth="advanced",
        max_results=8,
    )

    urls = [r["url"] for r in search["results"]]

    extracted = client.extract(
        urls=urls,
        extract_depth="advanced",
        format="markdown",
    )

    return extracted["results"]
```

---

## 14.3 文档站知识库同步

```text
Map 发现文档页
  ↓
Extract 批量提取
  ↓
切片
  ↓
Embedding
  ↓
写入向量库
```

```python
mapped = client.map(
    url="https://docs.tavily.com",
    select_paths=["/documentation/.*"],
    max_depth=3,
    limit=200,
)

pages = client.extract(
    urls=mapped["results"],
    extract_depth="advanced",
    format="markdown",
)

documents = [
    {
        "url": page["url"],
        "text": page["raw_content"],
    }
    for page in pages["results"]
]
```

---

## 14.4 官网竞品监控

```python
result = client.search(
    query="Tavily Brave Search API Exa AI search API new features",
    topic="news",
    time_range="month",
    include_domains=[
        "docs.tavily.com",
        "brave.com",
        "exa.ai",
    ],
    max_results=10,
    include_usage=True,
)

for r in result["results"]:
    print(r["published_date"], r["title"], r["url"])
```

---

## 14.5 深度研究报告

```python
result = client.research(
    input="""
    Research the current market of web search APIs for AI agents.
    Compare Tavily, Brave Search API, Exa, SerpAPI, and Perplexity API.
    Focus on agent use cases, retrieval quality, citations, latency, and pricing model.
    """,
    model="pro",
    citation_format="numbered",
)

print(result)
```

---

## 14.6 成本受控的批量任务

```python
queries = [
    "latest WADA anti-doping rule updates",
    "World Athletics testing protocol updates",
    "AI sports training monitoring systems",
]

all_results = []

for q in queries:
    result = client.search(
        query=q,
        search_depth="basic",
        max_results=3,
        include_usage=True,
    )
    all_results.append(result)

    print(q, result.get("usage"))
```

---

# 15. 关键参数速查

## Search 常用参数

| 参数                        | 作用                                  |
| ------------------------- | ----------------------------------- |
| `query`                   | 搜索问题                                |
| `search_depth`            | 搜索深度                                |
| `topic`                   | `general` 或 `news`                  |
| `time_range`              | `day` / `week` / `month` / `year` 等 |
| `days`                    | 最近 N 天                              |
| `start_date` / `end_date` | 指定时间区间                              |
| `max_results`             | 返回结果数量                              |
| `include_answer`          | 返回生成答案                              |
| `include_raw_content`     | 返回网页正文                              |
| `include_images`          | 返回图片                                |
| `include_domains`         | 只搜这些域名                              |
| `exclude_domains`         | 排除这些域名                              |
| `country`                 | 限定国家                                |
| `auto_parameters`         | 让 Tavily 自动调参                       |
| `exact_match`             | 精确匹配                                |
| `include_usage`           | 返回用量                                |

## Extract 常用参数

| 参数                  | 作用                   |
| ------------------- | -------------------- |
| `urls`              | 单个或多个 URL            |
| `query`             | 聚焦提取                 |
| `chunks_per_source` | 每个来源返回多少片段           |
| `extract_depth`     | `basic` / `advanced` |
| `format`            | `markdown` / `text`  |
| `include_images`    | 是否提取图片               |
| `include_favicon`   | 是否返回 favicon         |
| `timeout`           | 超时时间                 |
| `include_usage`     | 返回消耗                 |

## Map / Crawl 常用参数

| 参数                | 作用         |
| ----------------- | ---------- |
| `url`             | 起始 URL     |
| `instructions`    | 自然语言抓取指令   |
| `max_depth`       | 最大深度       |
| `max_breadth`     | 每层最大广度     |
| `limit`           | 最大页面数      |
| `select_paths`    | 只包含路径      |
| `exclude_paths`   | 排除路径       |
| `select_domains`  | 只包含域名      |
| `exclude_domains` | 排除域名       |
| `allow_external`  | 是否允许外链     |
| `extract_depth`   | Crawl 提取深度 |
| `format`          | 输出格式       |
| `include_usage`   | 返回消耗       |

---

# 16. 成本和质量控制

官方最佳实践里有几条很关键：query 尽量控制在 400 字符以内；复杂问题要拆成多个 query；`max_results` 不要盲目拉高；需要全文时优先 Search → Extract；`auto_parameters` 可能自动开启 advanced 搜索从而增加成本；`exact_match` 会提高精确度但可能减少结果。([docs.tavily.com][4])

## 16.1 不要把一个复杂任务塞进一个 query

差：

```python
client.search("""
Please research all current Tavily features, compare with Brave,
analyze pricing, SDK, MCP, CLI, RAG, integrations, and give examples.
""")
```

好：

```python
queries = [
    "Tavily Search API documentation",
    "Tavily Extract API documentation",
    "Tavily MCP Server documentation",
    "Tavily CLI documentation",
    "Tavily Hybrid RAG documentation",
]
```

## 16.2 不要默认全开 advanced

```python
# 成本更低，适合初筛
client.search(
    query="Tavily Search API",
    search_depth="basic",
    max_results=5,
)
```

```python
# 只有在需要深度结果时再开
client.search(
    query="compare AI search APIs for autonomous agents",
    search_depth="advanced",
    max_results=10,
)
```

## 16.3 Crawl 一定要设 limit

差：

```python
client.crawl("https://large-site.com")
```

好：

```python
client.crawl(
    url="https://large-site.com",
    max_depth=2,
    max_breadth=10,
    limit=50,
)
```

## 16.4 处理 robots / noindex

Tavily 文档里也说明了 crawler 如何识别自身，并提供了网站主通过 robots.txt、noindex 或联系 delisting 的方式控制抓取。做合规系统时，不要假设所有网页都应该被抓。([docs.tavily.com][17])

---

# 17. 给你的推荐封装：`TavilyResearchTool`

如果你要把 Tavily 放进“AI研究室 / 提示词工厂 / 体育智能系统”，我建议先封装成四层，而不是直接在业务里到处调用 API。

```text
TavilyResearchTool
│
├─ search_sources()
│  └─ 找候选来源
│
├─ extract_sources()
│  └─ 读取全文
│
├─ crawl_site()
│  └─ 抓文档站 / 官网
│
├─ research_report()
│  └─ 调 Research API 做报告初稿
│
└─ usage_guard()
   └─ 控制成本、记录 usage、设置阈值
```

### Python 母版

```python
from tavily import TavilyClient


class TavilyResearchTool:
    def __init__(self, api_key: str, project_id: str | None = None):
        kwargs = {"api_key": api_key}
        if project_id:
            kwargs["project_id"] = project_id

        self.client = TavilyClient(**kwargs)

    def search_sources(
        self,
        query: str,
        domains: list[str] | None = None,
        max_results: int = 5,
        depth: str = "basic",
    ):
        return self.client.search(
            query=query,
            search_depth=depth,
            include_domains=domains,
            max_results=max_results,
            include_usage=True,
        )

    def extract_sources(
        self,
        urls: list[str],
        query: str | None = None,
        advanced: bool = False,
    ):
        return self.client.extract(
            urls=urls,
            query=query,
            extract_depth="advanced" if advanced else "basic",
            format="markdown",
            include_usage=True,
        )

    def map_site(
        self,
        url: str,
        select_paths: list[str] | None = None,
        limit: int = 100,
    ):
        return self.client.map(
            url=url,
            select_paths=select_paths,
            max_depth=3,
            limit=limit,
            include_usage=True,
        )

    def crawl_site(
        self,
        url: str,
        instructions: str | None = None,
        limit: int = 50,
    ):
        return self.client.crawl(
            url=url,
            instructions=instructions,
            max_depth=2,
            max_breadth=10,
            limit=limit,
            extract_depth="basic",
            format="markdown",
            include_usage=True,
        )

    def research_report(
        self,
        prompt: str,
        model: str = "pro",
    ):
        return self.client.research(
            input=prompt,
            model=model,
            citation_format="numbered",
        )
```

---

# 18. 最小系统落地方案

## MVP 版本

```text
用户输入问题
  ↓
判断是否需要联网
  ↓
Search 找来源
  ↓
Extract 读取前 3-5 个高质量来源
  ↓
LLM 总结
  ↓
输出：
  - 结论
  - 来源
  - 不确定点
  - 下一步
```

## 进阶版本

```text
问题分类器
  ↓
[事实查询] Search
[网页正文] Extract
[站点采集] Map / Crawl
[复杂研究] Research
  ↓
来源评分
  ↓
正文提取
  ↓
RAG / LLM
  ↓
审计输出
  ↓
usage 记录
```

## 企业 / 项目版

```text
API Gateway
  ↓
Tavily Tool Router
  ├─ Search
  ├─ Extract
  ├─ Map
  ├─ Crawl
  ├─ Research
  └─ Usage Guard
  ↓
Source Quality Filter
  ↓
RAG / Knowledge Base
  ↓
LLM Answer Layer
  ↓
Audit Log
  ↓
Human Review
```

---

# 19. 我的使用建议

## 简单查资料

用：

```python
client.search(query, include_answer="basic")
```

## 做研究报告

用：

```python
client.research(input=research_question, model="pro")
```

但关键结论要回到原始来源核验。

## 做 RAG 数据采集

优先：

```text
Map → Extract
```

而不是一上来就 Crawl 全站。

## 做 Agent

优先：

```text
MCP Server
```

如果你要严格控成本、日志、权限，就自己封装 SDK 工具。

## 做长期系统

必须加：

```text
usage 记录
source 记录
失败 URL 记录
人工复核点
```

---

# 三根钉子

【钉子一：`Search → Extract → Answer` 这条链 → 最脆弱点不是搜索，而是“搜索摘要直接进入结论”，没读原文就容易错】

【钉子二：`Crawl / Research` 这类高级功能 → 隐藏机会成本是 credits 和噪声会一起放大，必须用 `limit`、路径过滤、usage 监控刹车】

【钉子三：Tavily 的核心价值是“给 AI 接实时网页证据” → 剥离所有工具后的致命前提是：你仍然要设计来源筛选、失败处理和人工复核，API 本身不替你完成事实审判】

[1]: https://docs.tavily.com/llms.txt "docs.tavily.com"
[2]: https://docs.tavily.com/documentation/quickstart "Quickstart - Tavily Docs"
[3]: https://docs.tavily.com/documentation/api-reference/endpoint/search "Tavily Search - Tavily Docs"
[4]: https://docs.tavily.com/documentation/best-practices/best-practices-search "Best Practices for Search - Tavily Docs"
[5]: https://docs.tavily.com/documentation/api-reference/endpoint/extract "Tavily Extract - Tavily Docs"
[6]: https://docs.tavily.com/documentation/api-reference/endpoint/map "Tavily Map - Tavily Docs"
[7]: https://docs.tavily.com/documentation/api-reference/endpoint/crawl "Tavily Crawl - Tavily Docs"
[8]: https://docs.tavily.com/documentation/api-reference/endpoint/research "Create Research Task - Tavily Docs"
[9]: https://docs.tavily.com/documentation/api-reference/endpoint/research-get "Get Research Task Status - Tavily Docs"
[10]: https://docs.tavily.com/documentation/api-reference/endpoint/research-streaming "Streaming - Tavily Docs"
[11]: https://docs.tavily.com/documentation/api-reference/endpoint/usage "Usage - Tavily Docs"
[12]: https://docs.tavily.com/sdk/python/quick-start "Quickstart - Tavily Docs"
[13]: https://docs.tavily.com/documentation/tavily-cli "Tavily CLI - Tavily Docs"
[14]: https://docs.tavily.com/documentation/mcp "Tavily MCP Server - Tavily Docs"
[15]: https://docs.tavily.com/documentation/agent-skills "Tavily Agent Skills - Tavily Docs"
[16]: https://docs.tavily.com/sdk/python/reference "SDK Reference - Tavily Docs"
[17]: https://docs.tavily.com/documentation/search-crawler "Tavily Search Crawler - Tavily Docs"
