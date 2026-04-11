# 接口字段字典 v1.1

## 1. 基本约定

- 协议：HTTP/HTTPS
- 数据格式：`application/json; charset=utf-8`
- 鉴权：当前 MVP 未启用，后续计划接入 `Authorization: Bearer <API_KEY>`
- 时间格式：ISO8601（例如 `2026-04-07T20:15:30+08:00`）
- 分页默认：`page=1`，`page_size=20`
- 除文件流接口外，统一响应结构：

```json
{
  "code": 0,
  "message": "ok",
  "request_id": "req_20260407_001",
  "data": {},
  "meta": {}
}
```

## 2. 通用响应字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| code | integer | 是 | 业务状态码，`0` 表示成功 |
| message | string | 是 | 结果说明 |
| request_id | string | 是 | 请求链路追踪 ID |
| data | object/array/null | 是 | 业务数据 |
| meta | object | 否 | 分页、耗时等扩展信息；当前多数接口未返回该字段 |

---

## 3. 接口清单

### 3.1 提交爬取任务

- 方法：`POST /v1/crawl/submit`

请求体：

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| url | string | 是 | - | 目标站点 URL（仅 http/https） |
| limit | integer | 否 | 50 | 最大抓取页面数，建议 1~1000 |
| depth | integer | 否 | 1 | 最大抓取深度，建议 1~5 |
| task_name | string | 否 | 自动生成 | 任务名 |
| renderer | string | 否 | http | `http` 或 `browser` |

响应 `data`：

| 字段 | 类型 | 说明 |
|---|---|---|
| task_id | string | 任务唯一标识 |
| fetch_mode | string | 实际抓取模式，`http` 或 `browser` |
| status | string | 初始状态，通常 `pending` |
| queued_count | integer | 已入队 URL 数 |

示例请求：

```json
{
  "url": "https://news.uestc.edu.cn/?n=UestcNews.Front.CategoryV2.Page&CatId=42",
  "limit": 100,
  "depth": 2,
  "task_name": "uestc_news_daily"
}
```

示例响应：

```json
{
  "code": 0,
  "message": "task created",
  "request_id": "req_20260407_001",
  "data": {
    "task_id": "task_20260407_001",
    "status": "pending",
    "queued_count": 1
  }
}
```

---

### 3.2 执行命令

- 方法：`POST /v1/command`

请求体：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| command | string | 是 | 命令文本 |
| request_id | string | 否 | 客户端传入追踪 ID，不传由服务端生成 |

响应 `data`：

| 字段 | 类型 | 说明 |
|---|---|---|
| output | string | 命令执行回显 |
| task_id | string/null | 若命令关联任务则返回 |

示例请求：

```json
{
  "command": "crawl pause task_id=task_20260407_001",
  "request_id": "req_manual_001"
}
```

---

### 3.3 查询任务状态

- 方法：`GET /v1/tasks/{task_id}`

路径参数：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| task_id | string | 是 | 任务 ID |

响应 `data`：

| 字段 | 类型 | 说明 |
|---|---|---|
| task_id | string | 任务 ID |
| fetch_mode | string | `http` 或 `browser` |
| status | string | `pending/running/paused/stopped/success/failed` |
| progress | number | 进度百分比，0~100 |
| total_count | integer | 总条数 |
| done_count | integer | 已完成条数 |
| failed_count | integer | 失败条数 |
| clean_done_count | integer | 已清洗条数 |
| created_at | string | 创建时间 |
| started_at | string/null | 开始时间 |
| ended_at | string/null | 结束时间 |

---

### 3.4 查询队列

- 方法：`GET /v1/tasks/{task_id}/queue`

查询参数：

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| state | string | 否 | all | `pending/running/done/failed/canceled/all` |

响应 `data`：

| 字段 | 类型 | 说明 |
|---|---|---|
| items | array | 队列项列表 |

队列项字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| id | integer | 队列项 ID |
| url | string | 队列 URL |
| state | string | 当前状态 |
| retry_count | integer | 重试次数 |
| next_run_at | string/null | 下次执行时间 |
| last_error | string/null | 最近失败原因 |
| updated_at | string | 更新时间 |

响应 `data` 额外字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| task_id | string | 任务 ID |
| state | string | 当前过滤条件 |
| total | integer | 当前返回项总数 |

---

### 3.5 查询结果集

- 方法：`GET /v1/tasks/{task_id}/results`

查询参数：

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| view | string | 否 | clean | `raw` 或 `clean` |
| page | integer | 否 | 1 | 页码 |
| page_size | integer | 否 | 20 | 每页数量 |
| q | string | 否 | - | 搜索关键词（标题/内容） |

`view=raw` 响应项字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| id | integer | 原始记录 ID |
| news_id | string | 业务 ID |
| news_date | string | 原始日期 |
| news_title | string | 原始标题 |
| news_content | string | 原始内容 |
| source_url | string | 来源 URL |
| fetched_at | string | 抓取时间 |

`view=clean` 响应项字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| id | integer | 清洗记录 ID |
| raw_id | integer | 对应原始记录 ID |
| clean_news_date | string | 清洗后日期 |
| clean_news_title | string | 清洗后标题 |
| clean_news_content | string | 清洗后内容 |
| dedup_key | string | 去重键 |
| clean_status | string | `clean_done/clean_failed` |
| cleaned_at | string | 清洗时间 |

---

### 3.6 导出结果

- 方法：`POST /v1/tasks/{task_id}/export`

请求体：

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| format | string | 是 | - | `json` 或 `csv` |

成功响应：

- 返回同步文件流，不包裹在统一 JSON 结构中
- `Content-Type`：
  - `application/json; charset=utf-8`
  - `text/csv; charset=utf-8`
- `Content-Disposition`：`attachment; filename="<task_id>_clean_results.<ext>"`
- 当前导出内容来源于 `clean_items`

失败响应：

- 仍使用统一 JSON 错误结构
- `task_id` 不存在时返回 `404 / code=2001`
- `format` 非法时返回 `400 / code=1001`

---

### 3.7 词云图

- 方法：`POST /v1/tasks/{task_id}/wordcloud`

请求体：

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| view | string | 否 | auto | `auto`、`clean`、`raw` |
| width | integer | 否 | 1200 | 图片宽度，320~2000 |
| height | integer | 否 | 720 | 图片高度，320~2000 |
| top_n | integer | 否 | 80 | 参与布局的热词数量，10~200 |

成功响应：

- 返回同步 `PNG` 文件流
- `Content-Type`：`image/png`
- `Content-Disposition`：`inline; filename="<task_id>_<view>_wordcloud.png"`
- 响应头：
  - `X-Wordcloud-View`：实际使用的数据来源视图
  - `X-Wordcloud-Top-Terms`：ASCII JSON 编码的高频词摘要

失败响应：

- 仍使用统一 JSON 错误结构
- 无可用文本时返回 `400 / code=1001`

---

### 3.8 实时事件流

- 方法：`GET /v1/events/stream?task_id=<task_id>`
- 协议：SSE（`text/event-stream`）
- 查询参数：

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| task_id | string | 是 | - | 任务 ID |
| after_id | integer | 否 | 0 | 仅返回大于该事件 ID 的新事件 |

事件结构：

```json
{
  "event_type": "crawl_item_success",
  "task_id": "task_20260407_001",
  "timestamp": "2026-04-07T20:16:00+08:00",
  "payload": {
    "url": "https://example.com/a",
    "message": "item parsed",
    "done_count": 12,
    "failed_count": 1
  }
}
```

事件类型：
- `task_created`
- `task_started`
- `task_resumed`
- `task_paused`
- `task_stopped`
- `queue_enqueued`
- `crawl_item_success`
- `crawl_item_failed`
- `clean_item_success`
- `clean_item_failed`
- `task_finished`

说明：

- 支持历史事件回放
- 支持 `after_id` 增量续传
- 任务进入终态后，服务端会在短暂空闲后自动关闭流
- 不存在的任务返回统一 JSON 错误结构，而不是 SSE 帧

---

### 3.9 健康检查

- 方法：`GET /v1/health`

响应 `data`：

| 字段 | 类型 | 说明 |
|---|---|---|
| status | string | `ok`/`degraded` |
| version | string | 服务版本 |
| timestamp | string | 服务端时间 |

---

## 4. 错误码说明

| code | 含义 |
|---|---|
| 0 | 成功 |
| 1001 | 参数非法 |
| 1002 | URL 非法或不允许 |
| 1003 | 不支持的命令 |
| 2001 | 任务不存在 |
| 2002 | 状态迁移非法 |
| 5000 | 系统内部错误 |

## 5. 命令语法规则

- 语法：`<module> <action> key=value ...`
- 参数分隔：空格
- Key/Value 分隔：`=`
- 非法命令处理：返回 `1003`
- 参数缺失处理：返回 `1001`
- `crawl start` 当前支持：`renderer=http|browser`

## 6. 页面入口

- 网页控制台首页：`GET /`
- 静态资源前缀：`/static/*`
- 当前前端为 FastAPI 同源挂载的原生静态页面，直接调用本文件中的后端接口
- 页面任务创建表单已支持选择 `HTTP` 或 `Browser / Playwright` 渲染模式

## 7. 动态渲染说明

- `renderer=browser` 使用 Playwright 的 Chromium 做动态页面渲染
- 运行前需要安装 Python 包 `playwright` 以及浏览器二进制
- 常用安装命令：`python -m playwright install chromium`
- 当前实现不包含 `stealth.js`、指纹伪装或规避检测逻辑
