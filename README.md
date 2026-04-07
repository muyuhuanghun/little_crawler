# 网页爬虫控制台 - PRD + TDD v1.0

## 1. 项目概述

本项目目标是把现有爬虫能力升级为“可在网页上控制的云服务工具”。

核心目标：
- 在网页输入目标网站 URL 发起爬取。
- 通过类命令行方式控制爬虫流程。
- 实时可视化待爬取/已爬取/失败队列。
- 对抓取数据进行清洗与规范化。
- 在同一网页展示控制过程与最终结果。
- 支持导出清洗后的 JSON/CSV。

---

## 2. 产品需求文档（PRD）

### 2.1 目标
- 支持网页输入 URL 并一键创建任务。
- 支持命令控制：开始/暂停/继续/停止/状态查询/队列查看/清洗/导出。
- 支持展示任务全生命周期与数据处理全流程。
- 支持按 `task_id`、`request_id` 全链路追踪。

### 2.2 MVP 范围
包含：
- 网页 URL 提交任务。
- 命令控制台。
- 任务与队列可视化。
- 基础清洗与去重。
- 结果表格展示与导出。

不包含：
- 多租户权限体系（RBAC）。
- 大规模分布式调度集群。
- 可视化拖拽规则编排器。

### 2.3 用户流程
1. 用户在网页输入 `url`、`limit`、`depth`。
2. 系统校验 URL 并创建 `task_id`。
3. 任务入队并开始爬取。
4. 页面通过实时事件更新进度与队列。
5. 原始数据进入清洗管道。
6. 用户查看清洗结果并导出 JSON/CSV。

### 2.4 命令控制台
支持命令：
- `help`
- `crawl start url=<...> limit=<...> depth=<...>`
- `crawl pause task_id=<...>`
- `crawl resume task_id=<...>`
- `crawl stop task_id=<...>`
- `task status task_id=<...>`
- `queue list task_id=<...> state=<pending|running|done|failed>`
- `clean run task_id=<...>`
- `export task_id=<...> format=<json|csv>`

回显规范：
- 统一字段：`code`、`message`、`request_id`、`output`、`task_id(可选)`。

### 2.5 页面信息架构
- 顶部：URL 输入区（`url`、`limit`、`depth`、开始按钮）。
- 左侧：命令控制台（输入框 + 历史命令 + 回显）。
- 中上：任务总览（运行中、排队中、失败、完成）。
- 中下：队列面板（待爬取 / 已爬取 / 失败）。
- 右侧：结果表格（原始/清洗切换）。
- 底部：实时事件流（终端样式）。

### 2.6 数据清洗要求
- 编码统一为 UTF-8。
- 去 HTML 标签与多余空白。
- 日期统一为 `YYYY-MM-DD`。
- 去重策略：优先 `news_id`，其次 `title+date` 哈希。
- 保留原始数据与清洗数据，支持对照查看。

### 2.7 非功能需求
- 正常场景 API 成功率 >= 99%。
- 命令回显目标 <= 1 秒。
- 查询接口 P95 < 1 秒。
- 任务支持暂停/恢复/重试。
- 过程支持全链路追踪。

### 2.8 安全要求
- 仅允许 `http/https`。
- SSRF 防护：禁止 localhost/内网/链路本地地址。
- MVP 使用 API Key 鉴权。
- 命令白名单 + 严格参数校验。
- 资源上限：最大深度、最大页面数、超时、重试次数。

### 2.9 验收标准
- 可通过网页输入 URL 并创建任务。
- 可通过命令控制任务生命周期。
- 页面可实时看到待爬取/已爬取/失败列表。
- 可查看清洗前后数据对照。
- 可导出 JSON/CSV。
- 全流程日志可在网页查看。

---

## 3. 技术设计文档（TDD）

### 3.1 总体架构
- 前端：网页控制台 + 实时看板。
- 后端 API：鉴权、校验、命令解析、查询接口。
- 调度执行层：任务管理、队列引擎、爬虫 Worker、清洗 Worker。
- 存储层：任务/队列/原始数据/清洗数据/日志。
- 实时通道：WebSocket（优先）或 SSE。

### 3.2 建议技术栈
- 后端：Python + FastAPI。
- 异步任务：Celery + Redis（MVP 可先用进程内队列）。
- 数据库：PostgreSQL（SQLite 仅用于本地原型）。
- 前端：React + 命令行控制组件。
- 实时推送：WebSocket。

### 3.3 模块拆分
- `api-gateway`：鉴权、路由、参数校验。
- `command-engine`：命令解析、白名单校验、执行分发。
- `task-service`：任务创建、状态迁移、进度统计。
- `queue-service`：URL 入队/出队、重试与退避。
- `crawler-worker`：页面抓取与解析。
- `clean-worker`：数据规范化与去重。
- `event-bus`：事件发布与前端推送。
- `export-service`：JSON/CSV 导出。

### 3.4 状态机设计
任务状态：
- `pending -> running -> success`
- `running -> paused -> running`
- `running|paused -> stopped`
- `running -> failed`

队列项状态：
- `pending -> running -> done`
- `running -> failed -> pending`（允许重试时）
- `running|pending -> canceled`（任务停止时）

清洗状态：
- `raw_ready -> clean_running -> clean_done`
- `clean_running -> clean_failed`

### 3.5 API 契约
- `POST /v1/crawl/submit`
  - 入参：`url`、`limit`、`depth`、`task_name`
  - 出参：`code`、`message`、`request_id`、`task_id`、`status`、`queued_count`
- `POST /v1/command`
  - 入参：`command`、`request_id`
  - 出参：`code`、`message`、`output`、`task_id?`
- `GET /v1/tasks/{task_id}`
  - 出参：任务状态/进度/计数/耗时
- `GET /v1/tasks/{task_id}/queue`
  - 出参：pending/running/done/failed 列表（分页）
- `GET /v1/tasks/{task_id}/results?view=raw|clean&page=&page_size=&q=`
  - 出参：分页结果
- `POST /v1/tasks/{task_id}/export`
  - 入参：`format=json|csv`
  - 出参：`download_id` 或 `download_url`
- `GET /v1/events/stream?task_id=...`
  - 出参：实时事件流（WebSocket/SSE）
- `GET /v1/health`
  - 出参：健康状态/版本/时间戳

### 3.6 数据模型
`tasks`
- `task_id`、`task_name`、`root_url`、`status`、`limit`、`depth`
- `total_count`、`done_count`、`failed_count`、`clean_done_count`
- `created_at`、`started_at`、`ended_at`

`queue_items`
- `id`、`task_id`、`url`、`state`、`retry_count`、`priority`
- `next_run_at`、`last_error`、`created_at`、`updated_at`
- 唯一键：`(task_id, url)`

`raw_items`
- `id`、`task_id`、`news_id`、`news_date`、`news_title`、`news_content`
- `source_url`、`fetched_at`、`raw_payload_json`

`clean_items`
- `id`、`raw_id`、`task_id`
- `clean_news_date`、`clean_news_title`、`clean_news_content`
- `dedup_key`、`clean_status`、`cleaned_at`
- 唯一键：`(task_id, dedup_key)`

`command_logs`
- `id`、`request_id`、`command`、`result_code`、`result_message`、`created_at`

`event_logs`
- `id`、`task_id`、`event_type`、`payload_json`、`created_at`

### 3.7 事件类型
- `task_created`
- `queue_enqueued`
- `crawl_item_success`
- `crawl_item_failed`
- `clean_item_success`
- `clean_item_failed`
- `task_finished`

### 3.8 错误码
- `0`：成功
- `1001`：参数非法
- `1002`：URL 非法或不允许
- `1003`：不支持的命令
- `2001`：任务不存在
- `2002`：状态迁移非法
- `3001`：抓取超时
- `3002`：抓取请求失败
- `3003`：解析失败
- `4001`：清洗失败
- `5000`：系统内部错误

### 3.9 前后端联调要求
- 任务创建成功后前端保存 `task_id`。
- 前端优先通过事件流更新页面。
- 事件流断开时，3 秒轮询任务状态兜底。
- 队列面板和结果表需做事件更新与轮询结果一致性对账。

### 3.10 实施排期（2 周）
- Day 1-2：表结构 + 状态机 + `/submit` + `/tasks`
- Day 3-4：命令引擎 + `/command`
- Day 5-6：爬虫 Worker + 队列执行
- Day 7-8：清洗 Worker + 去重
- Day 9：实时事件流
- Day 10：前端联调
- Day 11：导出 + 审计日志
- Day 12-14：测试、压测、上线准备

### 3.11 测试方案
- 单元测试：命令解析、状态迁移、清洗规则。
- 集成测试：提交 -> 抓取 -> 清洗 -> 导出全链路。
- 安全测试：SSRF、命令注入、限流。
- 性能测试：100 URL 任务负载与实时更新稳定性。

---

## 4. 下一步

当前 README 可作为开发基线。

建议马上补齐：
- API 字段字典 v1.0。
- 核心数据表 SQL DDL 草案。
- 前端线框图 v1.0（输入区、命令区、队列区、结果区、事件流）。
