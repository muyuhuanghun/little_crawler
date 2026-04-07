# 接口字段字典 v1.0

## 1. 基本约定

- 协议：HTTP/HTTPS
- 数据格式：`application/json; charset=utf-8`
- 鉴权：`Authorization: Bearer <API_KEY>`
- 时间格式：ISO8601（例如 `2026-04-07T20:15:30+08:00`）
- 分页默认：`page=1`，`page_size=20`
- 统一响应结构：

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
| meta | object | 否 | 分页、耗时等扩展信息 |

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

响应 `data`：

| 字段 | 类型 | 说明 |
|---|---|---|
| task_id | string | 任务唯一标识 |
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
| state | string | 否 | all | `pending/running/done/failed` |
| page | integer | 否 | 1 | 页码 |
| page_size | integer | 否 | 20 | 每页数量 |

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

响应 `meta`：

| 字段 | 类型 | 说明 |
|---|---|---|
| page | integer | 当前页 |
| page_size | integer | 每页数量 |
| total | integer | 总记录数 |

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

响应 `data`：

| 字段 | 类型 | 说明 |
|---|---|---|
| download_id | string | 导出任务 ID |
| download_url | string | 下载地址（若同步可直接返回） |
| expires_at | string | 下载地址失效时间 |

---

### 3.7 实时事件流

- 方法：`GET /v1/events/stream?task_id=<task_id>`
- 协议：WebSocket 或 SSE（二选一，推荐 WebSocket）

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
- `queue_enqueued`
- `crawl_item_success`
- `crawl_item_failed`
- `clean_item_success`
- `clean_item_failed`
- `task_finished`

---

### 3.8 健康检查

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
| 3001 | 抓取超时 |
| 3002 | 抓取请求失败 |
| 3003 | 解析失败 |
| 4001 | 清洗失败 |
| 5000 | 系统内部错误 |

## 5. 命令语法规则

- 语法：`<module> <action> key=value ...`
- 参数分隔：空格
- Key/Value 分隔：`=`
- 非法命令处理：返回 `1003`
- 参数缺失处理：返回 `1001`
