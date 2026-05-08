# Brave Search API 用法攻略

结论先放前面：**Brave 现在不是一个简单的“搜索 API”，而是一套搜索增强工具箱**。你要按用途选：

| 你的目标                                         | 优先用什么        |
| -------------------------------------------- | ------------ |
| 做传统搜索页                                       | Web Search   |
| 给 Agent / RAG / 聊天机器人喂资料                     | LLM Context  |
| 直接拿带引用的答案                                    | Answers      |
| 搜新闻                                          | News Search  |
| 搜图片                                          | Image Search |
| 搜视频                                          | Video Search |
| 搜地点 / POI                                    | Place Search |
| 做搜索框自动补全                                     | Autosuggest  |
| 纠正用户拼写                                       | Spellcheck   |
| 控制搜索结果排序 / 屏蔽来源                              | Goggles      |
| 让 Codex / Cursor / Claude Code 等工具直接调用 Brave | Skills       |

Brave 官方说，它的 API 使用自有独立搜索索引，不依赖 Google 或 Bing，并覆盖 web、news、images、videos 和 AI 能力。([Brave][1])

---

# 1. 账号、Key、通用调用方式

## 1.1 创建 API Key

流程：

1. 进入 Brave Search API Dashboard。
2. 订阅对应 plan。
3. 到 API Keys 页面。
4. Add API Key。
5. 复制并安全保存。

官方特别强调：API Key 要当密码处理，不要提交到代码仓库，也不要暴露在前端。所有请求都要通过 `X-Subscription-Token` 请求头传 Key。([Brave][2])

---

## 1.2 通用 Python 封装

```python
import os
import requests

BRAVE_API_KEY = os.getenv("BRAVE_SEARCH_API_KEY")

BASE_URL = "https://api.search.brave.com/res"

HEADERS = {
    "Accept": "application/json",
    "Accept-Encoding": "gzip",
    "X-Subscription-Token": BRAVE_API_KEY,
}

def brave_get(path: str, params: dict):
    url = f"{BASE_URL}{path}"
    resp = requests.get(url, headers=HEADERS, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()

def brave_post(path: str, payload: dict):
    url = f"{BASE_URL}{path}"
    resp = requests.post(url, headers=HEADERS, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()
```

---

# 2. 价格与 Plan 选择

截至当前官方文档，Search plan 包含 Web Search、LLM Context、News、Videos、Images 等，价格标为 **5 美元 / 1000 requests**，容量为 **50 requests/s**；Answers plan 是完成型答案服务，价格标为 **4 美元 / 1000 queries + 输入/输出 token 费用**，容量为 **2 requests/s**。Spellcheck / Autosuggest 也有单独价格与 100 requests/s 容量。价格可能变化，实际以 Dashboard 为准。([Brave][3])

**我的建议：**

| 场景            | 建议                                      |
| ------------- | --------------------------------------- |
| 自己有回答生成模型     | 买 Search，用 LLM Context / Web Search 喂模型 |
| 想快速做“带引用答案”产品 | 买 Answers                               |
| 只做搜索框体验       | Autosuggest + Spellcheck                |
| 做垂直搜索引擎       | Search + Goggles                        |
| 做本地生活 / 地图类功能 | Place Search + Local POIs               |

---

# 3. Web Search：基础网页搜索

## 3.1 适用场景

Web Search 是传统搜索入口。适合：

* 搜网页链接；
* 做搜索结果页；
* 搜含网页、新闻、视频、FAQ、infobox、discussions、locations 的综合结果；
* 配合 `result_filter` 控制返回类型；
* 配合 `freshness` 做时间过滤；
* 配合 `goggles` 做重排序；
* 配合 `enable_rich_callback` 获取天气、股票、体育等 rich result。

官方说明 Web Search 可访问大规模网页索引，并支持新鲜结果、本地增强和 rich data enrichments。([Brave][4])

---

## 3.2 Endpoint

```text
GET  /v1/web/search
POST /v1/web/search
```

Web Search 的必填参数是 `q`，最大 400 字符、50 个词；`count` 最大 20，`offset` 最大 9；`freshness` 支持 `pd`、`pw`、`pm`、`py` 和自定义日期范围；`result_filter` 可控制返回 `web`、`news`、`videos`、`locations`、`faq`、`infobox` 等类型。([Brave][5])

---

## 3.3 最小示例

```python
data = brave_get("/v1/web/search", {
    "q": "artificial intelligence",
    "country": "US",
    "search_lang": "en",
    "count": 10,
})

for item in data.get("web", {}).get("results", []):
    print(item["title"], item["url"])
```

---

## 3.4 中文搜索示例

```python
data = brave_get("/v1/web/search", {
    "q": "大模型 RAG 架构 最佳实践",
    "country": "CN",
    "search_lang": "zh",
    "ui_lang": "zh-CN",
    "count": 10,
    "safesearch": "moderate",
})
```

---

## 3.5 搜最近 7 天内容

```python
data = brave_get("/v1/web/search", {
    "q": "OpenAI API latest model update",
    "freshness": "pw",   # pd=24小时, pw=7天, pm=31天, py=365天
    "count": 10,
})
```

`freshness` 的日期过滤逻辑按网页内容报告的发布时间或修改时间判断，官方支持过去 24 小时、7 天、31 天、365 天和自定义区间。([Brave][5])

---

## 3.6 只要 Web 结果，不要综合结果

```python
data = brave_get("/v1/web/search", {
    "q": "AI governance framework",
    "result_filter": "web",
    "count": 10,
})
```

---

## 3.7 同时要 Web + News + Videos

```python
data = brave_get("/v1/web/search", {
    "q": "humanoid robot latest progress",
    "result_filter": "web,news,videos",
    "count": 10,
})
```

---

## 3.8 使用搜索操作符

Brave 支持 `site:`、`filetype:`、`ext:`、`intitle:`、`inbody:`、`lang:`、`loc:`、`+`、`-`、精确短语、`AND`、`OR`、`NOT` 等操作符。官方提醒这些 operators 仍属于实验阶段，复杂组合可能表现不稳定。([Brave][6])

```python
data = brave_get("/v1/web/search", {
    "q": 'RAG evaluation filetype:pdf site:edu "retrieval augmented generation"',
    "count": 10,
    "operators": True,
})
```

常用查询模板：

```text
site:openai.com API pricing
filetype:pdf anti-doping annual report
intitle:documentation python asyncio site:docs.python.org
AI startup -google -microsoft -amazon
visa loc:gb AND lang:en
```

---

# 4. LLM Context：给 Agent / RAG 用的搜索上下文

## 4.1 适用场景

这是 Brave 当前最适合 AI 系统的搜索接口。

Web Search 返回的是“搜索结果列表”；**LLM Context 返回的是模型可直接消费的预抽取内容**，包括文本片段、结构化内容、来源元数据等。官方明确说它面向 AI Agents、RAG pipelines、chatbots、fact checking、content research 等场景。([Brave][7])

一句话：
**人看结果页 → Web Search。
模型读材料 → LLM Context。**

---

## 4.2 Endpoint

```text
GET  /v1/llm/context
POST /v1/llm/context
```

核心参数：

| 参数                                 | 作用                             |
| ---------------------------------- | ------------------------------ |
| `q`                                | 查询词，必填                         |
| `count`                            | 最多考虑多少搜索结果，最大 50               |
| `maximum_number_of_urls`           | 最多纳入多少 URL，最大 50               |
| `maximum_number_of_tokens`         | 上下文总 token 上限，默认 8192，最大 32768 |
| `maximum_number_of_snippets`       | 最多片段数，最大 256                   |
| `maximum_number_of_tokens_per_url` | 单 URL token 上限，最大 8192         |
| `context_threshold_mode`           | 内容筛选阈值模式                       |
| `freshness`                        | 时间过滤                           |
| `goggles`                          | 搜索重排序                          |
| `enable_local`                     | 是否启用本地结果召回                     |
| `enable_source_metadata`           | 是否返回来源站点名、favicon、thumbnail 等  |

这些参数来自官方 LLM Context API Reference。([Brave][8])

---

## 4.3 RAG 检索示例

```python
context = brave_get("/v1/llm/context", {
    "q": "latest RAG evaluation benchmarks 2025",
    "country": "US",
    "search_lang": "en",
    "count": 20,
    "maximum_number_of_urls": 8,
    "maximum_number_of_tokens": 12000,
    "maximum_number_of_snippets": 80,
    "enable_source_metadata": True,
})

print(context.keys())
print(context.get("grounding"))
print(context.get("sources"))
```

---

## 4.4 技术问答示例

```python
context = brave_get("/v1/llm/context", {
    "q": "FastAPI streaming response example code",
    "count": 10,
    "maximum_number_of_tokens": 8000,
    "context_threshold_mode": "strict",
})
```

适合放到你的 Agent 里：

```python
def web_grounding_for_agent(question: str) -> str:
    data = brave_get("/v1/llm/context", {
        "q": question,
        "count": 20,
        "maximum_number_of_urls": 6,
        "maximum_number_of_tokens": 10000,
        "enable_source_metadata": True,
    })
    return str(data["grounding"])
```

---

## 4.5 使用建议

| 情况           | 参数建议                                   |
| ------------ | -------------------------------------- |
| 普通问答         | `maximum_number_of_tokens=8192`        |
| 深度研究         | `maximum_number_of_tokens=16000~32768` |
| 事实核查         | `context_threshold_mode="strict"`      |
| 想覆盖更多来源      | 提高 `maximum_number_of_urls`            |
| 想防止单一网页占满上下文 | 降低 `maximum_number_of_tokens_per_url`  |
| 做中文查询        | `search_lang="zh"`，`country` 视地区设定     |

---

# 5. Answers：直接生成带引用答案

## 5.1 适用场景

Answers 是完成型答案 API。它不是只返回搜索结果，而是返回 **AI-generated answers backed by real-time web search and verifiable sources**。官方强调它支持 OpenAI SDK 兼容、streaming、research mode、citations、entities 和 usage metadata。([Brave][9])

适合：

* 快速做问答机器人；
* 不想自己写 answer synthesis；
* 需要 citations；
* 需要多轮研究模式；
* 需要 OpenAI SDK 兼容接入。

---

## 5.2 Endpoint

```text
POST /v1/chat/completions
```

官方文档给的 base URL：

```text
https://api.search.brave.com/res/v1
```

Answers 使用 OpenAI-compatible endpoint。([Brave][9])

---

## 5.3 OpenAI SDK 示例

```python
from openai import OpenAI

client = OpenAI(
    api_key="YOUR_BRAVE_SEARCH_API_KEY",
    base_url="https://api.search.brave.com/res/v1",
)

completion = client.chat.completions.create(
    model="brave",
    messages=[
        {"role": "user", "content": "What are the best things to do in Paris with kids?"}
    ],
    stream=False,
)

print(completion.choices[0].message.content)
```

---

## 5.4 Streaming 示例

```python
from openai import AsyncOpenAI
import asyncio

client = AsyncOpenAI(
    api_key="YOUR_BRAVE_SEARCH_API_KEY",
    base_url="https://api.search.brave.com/res/v1",
)

async def main():
    stream = await client.chat.completions.create(
        model="brave",
        messages=[
            {"role": "user", "content": "Explain quantum computing with citations."}
        ],
        stream=True,
    )

    async for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            print(chunk.choices[0].delta.content, end="", flush=True)

asyncio.run(main())
```

---

## 5.5 Research Mode

Research Mode 会让模型进行多次搜索，更彻底，但成本更高、耗时更长。官方说明单搜索适合实时应用，多搜索适合更重的研究型问题。([Brave][9])

```python
completion = client.chat.completions.create(
    model="brave",
    messages=[
        {"role": "user", "content": "Give me a research-grade overview of AI agent memory systems."}
    ],
    stream=True,
    extra_body={
        "enable_research": True,
        "enable_citations": True,
        "country": "US",
        "language": "en",
    }
)
```

---

## 5.6 处理 citations / entities / usage

官方说明 streaming 时可能返回普通文本、`<citation>`、`<enum_item>` 和 `<usage>` 标签，需要开发者解析这些特殊消息。([Brave][9])

```python
import json

def parse_brave_stream_delta(delta: str):
    if delta.startswith("<citation>") and delta.endswith("</citation>"):
        payload = delta.removeprefix("<citation>").removesuffix("</citation>")
        return {"type": "citation", "data": json.loads(payload)}

    if delta.startswith("<enum_item>") and delta.endswith("</enum_item>"):
        payload = delta.removeprefix("<enum_item>").removesuffix("</enum_item>")
        return {"type": "entity", "data": json.loads(payload)}

    if delta.startswith("<usage>") and delta.endswith("</usage>"):
        payload = delta.removeprefix("<usage>").removesuffix("</usage>")
        return {"type": "usage", "data": json.loads(payload)}

    return {"type": "text", "data": delta}
```

---

## 5.7 什么时候不用 Answers？

| 情况         | 不建议用 Answers 的原因                                |
| ---------- | ----------------------------------------------- |
| 你要自己控制答案风格 | Answers 已经合成答案，控制空间小                            |
| 你要多模型交叉验证  | LLM Context 更适合把材料喂给不同模型                        |
| 你要做可审计研究链  | 建议自己保存 search query、source、context、model output |
| 你要极低延迟     | 默认 single search 可用，但 Research Mode 会变慢         |

---

# 6. News Search：新闻搜索

## 6.1 适用场景

News Search 使用专门新闻索引，适合新闻聚合、媒体监测、热点追踪、历史新闻研究。官方说明它支持新闻专用索引、freshness filtering、国家与语言选项、extra snippets。([Brave][10])

---

## 6.2 Endpoint

```text
GET  /v1/news/search
POST /v1/news/search
```

核心参数：

| 参数               | 作用                                |
| ---------------- | --------------------------------- |
| `q`              | 查询词                               |
| `search_lang`    | 搜索语言                              |
| `ui_lang`        | 界面语言                              |
| `country`        | 国家，也可 `ALL`                       |
| `safesearch`     | `off` / `moderate` / `strict`     |
| `count`          | 最大 50                             |
| `offset`         | 分页，最大 9                           |
| `freshness`      | `pd` / `pw` / `pm` / `py` / 自定义区间 |
| `extra_snippets` | 最多额外 5 个摘录                        |
| `goggles`        | 新闻源排序控制                           |
| `operators`      | 是否启用搜索操作符                         |

参数见官方 News API Reference。([Brave][11])

---

## 6.3 最近 7 天新闻

```python
news = brave_get("/v1/news/search", {
    "q": "AI regulation",
    "country": "US",
    "search_lang": "en",
    "freshness": "pw",
    "count": 20,
    "extra_snippets": True,
})

for item in news.get("results", []):
    print(item.get("title"), item.get("url"))
```

---

## 6.4 指定日期范围

```python
news = brave_get("/v1/news/search", {
    "q": "Paris Olympics anti-doping",
    "freshness": "2024-07-01to2024-08-31",
    "count": 20,
})
```

---

## 6.5 媒体监测示例

```python
news = brave_get("/v1/news/search", {
    "q": '"World Athletics" anti-doping OR "AIU"',
    "freshness": "pm",
    "count": 30,
    "operators": True,
})
```

---

# 7. Video Search：视频搜索

## 7.1 适用场景

Video Search 搜视频内容，适合教程检索、娱乐内容聚合、视频平台搜索、品牌视频监测。官方说明它有视频专用索引，支持 freshness、国家语言、Safe Search。([Brave][12])

---

## 7.2 Endpoint

```text
GET  /v1/videos/search
POST /v1/videos/search
```

核心参数与 News 类似：`q`、`search_lang`、`ui_lang`、`country`、`safesearch`、`count`、`offset`、`freshness`、`include_fetch_metadata`、`operators`。`count` 最大 50，`offset` 最大 9。([Brave][13])

---

## 7.3 视频教程搜索

```python
videos = brave_get("/v1/videos/search", {
    "q": "FastAPI tutorial streaming response",
    "country": "US",
    "search_lang": "en",
    "freshness": "py",
    "count": 10,
    "safesearch": "moderate",
})

for item in videos.get("results", []):
    print(item.get("title"), item.get("url"))
```

---

## 7.4 中文视频搜索

```python
videos = brave_get("/v1/videos/search", {
    "q": "大模型 RAG 教程",
    "country": "ALL",
    "search_lang": "zh",
    "ui_lang": "zh-CN",
    "count": 20,
})
```

---

# 8. Image Search：图片搜索

## 8.1 适用场景

Image Search 返回图片结果，适合图库搜索、素材发现、视觉参考、图片候选集。官方说明 Image Search 可从大规模图片索引检索，并且单次最多可取 200 张，默认 strict Safe Search。([Brave][14])

---

## 8.2 Endpoint

```text
GET /v1/images/search
```

核心参数：

| 参数            | 作用                         |
| ------------- | -------------------------- |
| `q`           | 查询词                        |
| `search_lang` | 语言                         |
| `country`     | 国家或 `ALL`                  |
| `safesearch`  | `off` / `strict`，默认 strict |
| `count`       | 最大 200                     |
| `spellcheck`  | 是否拼写修正                     |

---

## 8.3 图片搜索示例

```python
images = brave_get("/v1/images/search", {
    "q": "futuristic city concept art",
    "country": "ALL",
    "search_lang": "en",
    "count": 50,
    "safesearch": "strict",
})

for item in images.get("results", [])[:5]:
    print(item.get("title"), item.get("url"))
```

---

## 8.4 给创作找视觉参考

```python
images = brave_get("/v1/images/search", {
    "q": "ancient chinese armor museum reference",
    "country": "ALL",
    "search_lang": "en",
    "count": 30,
})
```

注意：这是“搜索已有图片”，不是生成图片，也不是自动授权使用。用于商业素材时还要单独处理版权。

---

# 9. Place Search：地点 / POI 搜索

## 9.1 适用场景

Place Search 专门找现实地点，不是找网页。适合：

* 附近咖啡馆；
* 酒店；
* 地标；
* 博物馆；
* 城市景点；
* 本地生活服务；
* POI 推荐系统。

官方说明 Place Search 面向 physical world locations，支持坐标、地点名、radius bias，并有 2 亿+ indexed places；返回可包含 POI、城市、地址、街道和 mixed ordering。([Brave][15])

---

## 9.2 Endpoint

```text
GET /v1/local/place_search
```

核心参数：

| 参数                       | 作用                          |
| ------------------------ | --------------------------- |
| `q`                      | 搜索词，可空；为空时返回区域内一般 POI       |
| `latitude` / `longitude` | 坐标                          |
| `location`               | 地点字符串，替代经纬度                 |
| `radius`                 | 围绕坐标的距离偏置，不是严格半径            |
| `count`                  | 最大 50                       |
| `country`                | 国家                          |
| `search_lang`            | 搜索语言                        |
| `ui_lang`                | 界面语言                        |
| `units`                  | `metric` / `imperial`       |
| `safesearch`             | 安全过滤                        |
| `spellcheck`             | 拼写修正                        |
| `geoloc`                 | `<latitude>x<longitude>` 格式 |

官方特别说明 `radius` 是 bias，不是严格限定搜索半径。([Brave][16])

---

## 9.3 附近咖啡馆

```python
places = brave_get("/v1/local/place_search", {
    "q": "coffee shops",
    "latitude": 37.7749,
    "longitude": -122.4194,
    "radius": 1000,
    "count": 20,
    "units": "metric",
})

for p in places.get("results", []):
    print(p.get("name"), p.get("address"))
```

---

## 9.4 按城市搜索景点

```python
places = brave_get("/v1/local/place_search", {
    "q": "museums",
    "location": "Tokyo, Japan",
    "country": "JP",
    "search_lang": "en",
    "count": 20,
})
```

---

## 9.5 Explore Mode：不提供 q

```python
places = brave_get("/v1/local/place_search", {
    "latitude": 35.6812,
    "longitude": 139.7671,
    "radius": 2000,
    "count": 20,
})
```

适合“我在东京站附近，有什么可去的地方”。

---

# 10. Local POIs：根据 Web Search 返回的 location ids 获取 POI 详情

## 10.1 适用场景

Web Search 或 Place Search 可能返回 location IDs。Local POIs 用这些 ids 再取详细 POI 信息。

官方说明 `/local/pois` 的 `ids` 是必填，location id 只在约 8 小时内有效；Web Search 文档还提醒不要长期保存这些 ephemeral ids。([Brave][17])

---

## 10.2 Endpoint

```text
GET /v1/local/pois
```

---

## 10.3 示例

```python
poi = brave_get("/v1/local/pois", {
    "ids": "loc4FNMQJNOOCVHEB7UBOLN354ZYIDIYJ3RPRETERRY=",
    "search_lang": "en",
    "ui_lang": "en-US",
    "units": "metric",
})

print(poi)
```

---

## 10.4 正确流程

```text
第一步：Web Search / Place Search 搜 “coffee near me”
第二步：从 locations / results 里取 id
第三步：马上调用 /local/pois
第四步：展示详情
第五步：不要把 id 存数据库长期复用
```

---

# 11. POI Descriptions：获取地点描述

## 11.1 适用场景

Local POIs 更偏结构化详情。POI Descriptions 更适合拿地点介绍、摘要描述，用于地点详情页、旅游助手、本地推荐 Agent。

官方说明 `/local/descriptions` 只接受 `ids`，同样是 location identifiers。([Brave][18])

---

## 11.2 Endpoint

```text
GET /v1/local/descriptions
```

---

## 11.3 示例

```python
desc = brave_get("/v1/local/descriptions", {
    "ids": "loc4FNMQJNOOCVHEB7UBOLN354ZYIDIYJ3RPRETERRY=",
})

print(desc)
```

---

# 12. Rich Search：天气、股票、体育等实时富结果

## 12.1 适用场景

Rich Search 不是直接拿普通网页结果，而是拿某些查询对应的实时富结果，比如：

* weather in london；
* stock price；
* sports scores；
* 其他 rich verticals。

官方说明流程是：先调用 Web Search 并设置 `enable_rich_callback=true`，从返回中拿 `callback_key`，再调用 `/v1/web/rich`。([Brave][19])

---

## 12.2 两步流程

### 第一步：Web Search 开启 rich callback

```python
first = brave_get("/v1/web/search", {
    "q": "weather in London",
    "enable_rich_callback": True,
})

callback_key = first.get("rich", {}).get("callback_key")
print(callback_key)
```

### 第二步：用 callback_key 获取 rich result

```python
rich = brave_get("/v1/web/rich", {
    "callback_key": callback_key,
})

print(rich)
```

---

## 12.3 使用建议

| 场景         | 建议                       |
| ---------- | ------------------------ |
| 天气、股价、体育比分 | 优先走 Rich Search          |
| 普通新闻解释     | 用 News / LLM Context     |
| 需要自己生成答案   | Rich Search 结果再喂给模型      |
| 需要用户可见卡片   | Rich Search 返回结构化结果后前端渲染 |

---

# 13. Autosuggest：搜索框自动补全

## 13.1 适用场景

Autosuggest 用于用户输入过程中实时提示 query。官方说明它支持实时补全、国家和语言偏好、rich enrichments、entity detection；rich suggestions 需要对应的付费 Autosuggest 订阅。([Brave][20])

---

## 13.2 Endpoint

```text
GET /v1/suggest/search
```

核心参数：

| 参数        | 作用                        |
| --------- | ------------------------- |
| `q`       | 用户当前输入                    |
| `lang`    | 语言 hint                   |
| `country` | 国家 hint                   |
| `count`   | 最多 20，默认 5                |
| `rich`    | 是否启用 enriched suggestions |

---

## 13.3 搜索框补全示例

```python
suggestions = brave_get("/v1/suggest/search", {
    "q": "rag eval",
    "lang": "en",
    "country": "US",
    "count": 8,
    "rich": False,
})

print(suggestions)
```

---

## 13.4 前端调用节流建议

不要每敲一个字都打 API。建议：

```text
输入长度 < 2：不请求
输入停顿 150~300ms：请求
相同 q + lang + country：缓存 5~30 分钟
用户按回车：走 Web Search / LLM Context
```

---

# 14. Spellcheck：搜索词纠错

## 14.1 适用场景

Spellcheck 用来纠正用户 query。官方说明它适合搜索应用、Did you mean、query suggestions、query data quality 等。([Brave][21])

---

## 14.2 Endpoint

```text
GET /v1/spellcheck/search
```

核心参数：

| 参数        | 作用      |
| --------- | ------- |
| `q`       | 待纠错短语   |
| `lang`    | 语言 hint |
| `country` | 国家 hint |

---

## 14.3 示例

```python
fixed = brave_get("/v1/spellcheck/search", {
    "q": "retrival agumented genration",
    "lang": "en",
    "country": "US",
})

print(fixed)
```

---

## 14.4 与 Web Search 组合

```python
def search_with_spellcheck(user_query: str):
    corrected = brave_get("/v1/spellcheck/search", {
        "q": user_query,
        "lang": "en",
        "country": "US",
    })

    # 具体字段以实际响应为准，这里示意
    q2 = corrected.get("query", {}).get("altered") or user_query

    return brave_get("/v1/web/search", {
        "q": q2,
        "count": 10,
    })
```

---

# 15. Goggles：自定义搜索排序和过滤

## 15.1 适用场景

Goggles 是 Brave 很有价值的功能。它不是普通参数，而是一个“小型排序规则系统”。

官方说明 Goggles 可用 DSL 对搜索结果进行 boost、downrank、discard，并可按 URL pattern、domain 等规则控制排序；它可用于 Web Search 和 News Search。([Brave][22])

适合：

* 垂直搜索引擎；
* 只信任特定来源；
* 屏蔽内容农场；
* 新闻源权重控制；
* 品牌监测；
* 学术搜索过滤。

---

## 15.2 Hosted Goggles 示例

```python
data = brave_get("/v1/web/search", {
    "q": "programming tutorials",
    "goggles": "https://raw.githubusercontent.com/brave/goggles-quickstart/main/goggles/tech_blogs.goggle",
})
```

官方支持 hosted Goggles URL、inline specification，以及多个 Goggles 混合使用。复杂规则建议用 hosted file，避免 URL 长度限制。([Brave][22])

---

## 15.3 多个 Goggles

```python
import requests

url = "https://api.search.brave.com/res/v1/web/search"

params = [
    ("q", "rust programming"),
    ("goggles", "https://example.com/goggle1.goggle"),
    ("goggles", "https://example.com/goggle2.goggle"),
]

resp = requests.get(url, headers=HEADERS, params=params)
print(resp.json())
```

---

## 15.4 Inline Goggles

```python
data = brave_get("/v1/web/search", {
    "q": "web development",
    "goggles": "$boost=3,site=dev.to",
})
```

---

## 15.5 `.goggle` 文件示例

```text
! name: AI Research Sources
! description: Boost trusted AI research sources and discard low-quality aggregators
! public: false
! author: KARAS

$boost=5,site=arxiv.org
$boost=5,site=openreview.net
$boost=4,site=aclanthology.org
$boost=4,site=docs.anthropic.com
$boost=4,site=platform.openai.com
$downrank=4,site=medium.com
$discard,site=spam-example.com
```

官方 Goggles actions 包括 `$boost`、`$boost=N`、`$downrank`、`$downrank=N`、`$discard`；规则冲突时，`$discard` 优先，其次 boost 优先于 downrank，高强度值优先于低强度值。([Brave][22])

---

## 15.6 限制

官方列出的限制包括：单个 Goggles 文件最大 2MB、最多 100,000 条指令、每条指令最长 500 字符、通配符和 caret 数量有限。生产环境建议用 Git 做版本控制。([Brave][22])

---

# 16. Search Operators：高级查询语法

## 16.1 常用操作符表

| 操作符         | 作用      | 例子                      |
| ----------- | ------- | ----------------------- |
| `ext:`      | 文件扩展名   | `manual ext:pdf`        |
| `filetype:` | 文件类型    | `report filetype:pdf`   |
| `intitle:`  | 标题中包含   | `intitle:guide`         |
| `inbody:`   | 正文中包含   | `inbody:"exact phrase"` |
| `inpage:`   | 标题或正文包含 | `inpage:keyword`        |
| `lang:`     | 语言过滤    | `lang:zh`               |
| `loc:`      | 地区过滤    | `loc:ca`                |
| `site:`     | 站点过滤    | `site:example.com`      |
| `+`         | 强制包含    | `+required`             |
| `-`         | 排除      | `-unwanted`             |
| `""`        | 精确短语    | `"exact phrase"`        |
| `AND`       | 逻辑与     | `term1 AND term2`       |
| `OR`        | 逻辑或     | `term1 OR term2`        |
| `NOT`       | 逻辑非     | `term NOT excluded`     |

以上表来自官方 operator reference。([Brave][6])

---

## 16.2 学术搜索

```python
data = brave_get("/v1/web/search", {
    "q": 'climate change filetype:pdf site:edu intitle:2024',
    "count": 10,
})
```

---

## 16.3 技术文档搜索

```python
data = brave_get("/v1/web/search", {
    "q": 'python "asyncio" intitle:documentation site:docs.python.org',
    "count": 10,
})
```

---

## 16.4 竞品监测

```python
data = brave_get("/v1/web/search", {
    "q": 'AI startup -google -microsoft -amazon -meta',
    "count": 20,
})
```

---

# 17. Summarizer Search：旧接口，不建议新项目使用

官方文档明确写了：**Summarizer Search API is deprecated in favor of new and improved Answers API**。老 Pro AI plan 用户可继续使用，但新项目应该直接用 Answers。([Brave][23])

如果你看到旧教程里有 Summarizer：

```text
不要优先接。
直接迁移到 Answers。
```

---

# 18. Skills：给 AI 编程工具用的 Brave 技能包

## 18.1 适用场景

Skills 是 Brave 给 AI coding agents 准备的可复用工作流资源。官方说明它支持 Claude Code、Cursor、GitHub Copilot、Codex、Gemini CLI、VS Code、Windsurf、OpenClaw、Cline、Goose、Roo Code 等支持 Agent Skills 标准的工具。([Brave][24])

这对你很有用：
你以后如果做 **OpenClaw / Hermes Agent / Codex / Cursor** 的搜索工具封装，可以直接拿 Brave Skills 当外部搜索能力层。

---

## 18.2 Codex 配置示例

官方给的 Codex 配置方式是写入 `~/.codex/config.toml`：([Brave][24])

```toml
[shell_environment_policy]
set = { BRAVE_SEARCH_API_KEY = "your-key" }
```

---

## 18.3 Cursor 配置示例

```bash
echo 'export BRAVE_SEARCH_API_KEY="your-key"' >> .envrc
direnv allow
```

或者：

```bash
export BRAVE_SEARCH_API_KEY="your-key"
```

然后重启 Cursor。

---

# 19. 推荐系统架构：Brave 放在哪一层？

## 19.1 最小 Agent 搜索架构

```text
用户问题
  ↓
Query Router
  ├─ 普通网页信息 → Web Search
  ├─ 模型需要上下文 → LLM Context
  ├─ 直接答案 → Answers
  ├─ 新闻 → News Search
  ├─ 地点 → Place Search
  ├─ 图片 → Image Search
  ├─ 视频 → Video Search
  └─ 搜索框输入中 → Autosuggest / Spellcheck
  ↓
Source Filter / Reranker
  ↓
LLM
  ↓
Citation Builder
  ↓
最终答案
```

---

## 19.2 给你的项目的落地建议

| 你的方向             | Brave API 组合                                                  |
| ---------------- | ------------------------------------------------------------- |
| AI研究室深度研究 Agent  | LLM Context + Web Search + News + Goggles                     |
| 提示词工厂            | Web Search 查官方文档，LLM Context 给模型喂材料                           |
| AI合规审计           | News Search 追踪政策新闻，Web Search 查法规原文，Goggles 固定权威源             |
| 体育智能系统           | Web Search 查规则 / 赛事 / 文档，Rich Search 查实时体育信息，News Search 监控舆情 |
| 小说资料考据           | Image Search 找视觉参考，Web Search 查历史资料，LLM Context 汇总素材          |
| 本地生活 Agent       | Place Search + Local POIs + POI Descriptions                  |
| 浏览器搜索框 / App 搜索框 | Autosuggest + Spellcheck + Web Search                         |

---

# 20. 一个可直接复用的 Brave Search Tool 类

```python
import os
import requests
from typing import Any, Dict, Optional

class BraveSearchClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("BRAVE_SEARCH_API_KEY")
        if not self.api_key:
            raise ValueError("Missing BRAVE_SEARCH_API_KEY")

        self.base = "https://api.search.brave.com/res"
        self.headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": self.api_key,
        }

    def _get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        resp = requests.get(
            f"{self.base}{path}",
            headers=self.headers,
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def web(self, q: str, **kwargs):
        return self._get("/v1/web/search", {"q": q, **kwargs})

    def llm_context(self, q: str, **kwargs):
        return self._get("/v1/llm/context", {"q": q, **kwargs})

    def news(self, q: str, **kwargs):
        return self._get("/v1/news/search", {"q": q, **kwargs})

    def videos(self, q: str, **kwargs):
        return self._get("/v1/videos/search", {"q": q, **kwargs})

    def images(self, q: str, **kwargs):
        return self._get("/v1/images/search", {"q": q, **kwargs})

    def places(self, q: str = "", **kwargs):
        return self._get("/v1/local/place_search", {"q": q, **kwargs})

    def local_pois(self, ids: str, **kwargs):
        return self._get("/v1/local/pois", {"ids": ids, **kwargs})

    def poi_descriptions(self, ids: str):
        return self._get("/v1/local/descriptions", {"ids": ids})

    def suggest(self, q: str, **kwargs):
        return self._get("/v1/suggest/search", {"q": q, **kwargs})

    def spellcheck(self, q: str, **kwargs):
        return self._get("/v1/spellcheck/search", {"q": q, **kwargs})

    def rich(self, callback_key: str):
        return self._get("/v1/web/rich", {"callback_key": callback_key})
```

调用：

```python
client = BraveSearchClient()

# 传统搜索
print(client.web("Brave Search API documentation", count=5))

# RAG 上下文
print(client.llm_context(
    "AI agent memory architecture",
    maximum_number_of_tokens=12000,
    maximum_number_of_urls=6,
))

# 新闻
print(client.news("AI regulation", freshness="pw", count=10))

# 地点
print(client.places(
    "coffee shops",
    latitude=35.6812,
    longitude=139.7671,
    radius=1500,
    country="JP",
))
```

---

# 21. 错误处理建议

官方 API Reference 多数接口都会列出常见错误码，如 400、403、404、422、429；Web Search 也列出 404、422、429。([Brave][5])

建议统一封装：

```python
import time
import requests

def safe_brave_get(path, params, retries=3):
    for i in range(retries):
        try:
            return brave_get(path, params)

        except requests.HTTPError as e:
            status = e.response.status_code

            if status == 429:
                # rate limit
                time.sleep(1.5 * (i + 1))
                continue

            if status in (400, 422):
                raise ValueError(f"Bad Brave request: {e.response.text}")

            if status in (401, 403):
                raise PermissionError("Brave API key invalid or plan not allowed")

            raise

    raise RuntimeError("Brave API failed after retries")
```

---

# 22. 选型口诀

```text
要链接 → Web Search
要模型可读材料 → LLM Context
要现成带引用答案 → Answers
要新闻 → News Search
要视频 → Video Search
要图片 → Image Search
要地点 → Place Search
要地点详情 → Local POIs
要地点介绍 → POI Descriptions
要天气/股票/体育富结果 → Rich Search
要搜索框补全 → Autosuggest
要纠错 → Spellcheck
要控制来源排序 → Goggles
要 AI 编程工具直接接入 → Skills
```

---

# 23. 最容易踩的坑

| 坑                                 | 后果               | 修正                   |
| --------------------------------- | ---------------- | -------------------- |
| Agent 直接用 Web Search              | 拿到一堆链接，模型还要自己猜重点 | 改用 LLM Context       |
| 把 Answers 当检索接口                   | 结果好看但可控性下降       | 需要自控合成时用 LLM Context |
| POI id 长期保存                       | 过期失效             | 只短期使用，约 8 小时内消耗      |
| 没处理 429                           | 高并发崩             | 加重试、限流、缓存            |
| 搜索框每字请求                           | 成本和延迟都炸          | debounce + cache     |
| 没设置 `country/search_lang/ui_lang` | 中文或地区结果偏差        | 显式设置                 |
| 把 Image Search 当素材授权              | 版权风险             | 只当发现入口，不等于授权         |
| Goggles 规则过复杂                     | 排序难解释            | 先小规则，再版本化测试          |
| Research Mode 默认开启                | 慢且贵              | 只给深研任务开启             |

---

# 三根钉子

【钉子一：LLM Context vs Web Search → 执行链上最脆弱的断裂点是“把给人看的搜索结果误当成给模型用的上下文”】

【钉子二：Answers 的便利性 → 隐藏的机会成本是你会失去一部分检索、排序、证据筛选和答案生成控制权】

【钉子三：Brave API 接入价值 → 剥离所有工具后的致命前提是：你的系统必须先会判断“这次到底是在找链接、找证据、找地点，还是直接要答案”】

[1]: https://api-dashboard.search.brave.com/documentation "Brave Search - API"
[2]: https://api-dashboard.search.brave.com/documentation/quickstart "Brave Search - API"
[3]: https://api-dashboard.search.brave.com/documentation/pricing "Brave Search - API"
[4]: https://api-dashboard.search.brave.com/documentation/services/web-search "Brave Search - API"
[5]: https://api-dashboard.search.brave.com/api-reference/web/search/get "Brave Search - API"
[6]: https://api-dashboard.search.brave.com/documentation/resources/search-operators "Brave Search - API"
[7]: https://api-dashboard.search.brave.com/documentation/services/llm-context "Brave Search - API"
[8]: https://api-dashboard.search.brave.com/api-reference/summarizer/llm_context/get "Brave Search - API"
[9]: https://api-dashboard.search.brave.com/documentation/services/grounding "Brave Search - API"
[10]: https://api-dashboard.search.brave.com/documentation/services/news-search "Brave Search - API"
[11]: https://api-dashboard.search.brave.com/api-reference/news/news_search/get "Brave Search - API"
[12]: https://api-dashboard.search.brave.com/documentation/services/video-search "Brave Search - API"
[13]: https://api-dashboard.search.brave.com/api-reference/videos/video_search/get "Brave Search - API"
[14]: https://api-dashboard.search.brave.com/documentation/services/image-search "Brave Search - API"
[15]: https://api-dashboard.search.brave.com/documentation/services/place-search "Brave Search - API"
[16]: https://api-dashboard.search.brave.com/api-reference/web/place_search "Brave Search - API"
[17]: https://api-dashboard.search.brave.com/api-reference/web/local_pois "Brave Search - API"
[18]: https://api-dashboard.search.brave.com/api-reference/web/poi_descriptions "Brave Search - API"
[19]: https://api-dashboard.search.brave.com/api-reference/web/rich_search "Brave Search - API"
[20]: https://api-dashboard.search.brave.com/documentation/services/suggest "Brave Search - API"
[21]: https://api-dashboard.search.brave.com/documentation/services/spellcheck "Brave Search - API"
[22]: https://api-dashboard.search.brave.com/documentation/resources/goggles "Brave Search - API"
[23]: https://api-dashboard.search.brave.com/documentation/services/summarizer "Brave Search - API"
[24]: https://api-dashboard.search.brave.com/documentation/resources/skills "Brave Search - API"
