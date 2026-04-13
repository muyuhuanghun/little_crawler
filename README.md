# 网页爬虫控制台需求与技术文档（PRD + TDD v1.1）

## 1. 项目定位

本项目的最终目标不是“本地可运行脚本”，而是“可部署到服务器、可供他人访问的网站型爬虫控制台”。

目标形态：
- 用户通过浏览器访问网站。
- 前端页面提交 URL、控制任务、查看队列和结果。
- 后端 API 负责鉴权、命令解析、任务调度、结果查询。
- 爬虫与清洗逻辑在服务端执行。
- 项目最终可部署到云服务器，并通过域名或公网 IP 访问。

核心能力：
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
- 支持部署到云端服务器供他人访问。

### 2.2 MVP 范围
包含：
- 网页 URL 提交任务。
- 命令控制台。
- 任务与队列可视化。
- 基础清洗与去重。
- 结果表格展示与导出。
- 单机部署版本的公网访问能力。

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
- `crawl start url=<...> limit=<...> depth=<...> [task_name=<...>]`
- `crawl pause task_id=<...>`
- `crawl resume task_id=<...>`
- `crawl stop task_id=<...>`
- `task status task_id=<...>`
- `queue list task_id=<...> state=<pending|running|done|failed|canceled|all>`
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
- 部署后支持公网稳定访问。

### 2.8 安全要求
- 仅允许 `http/https`。
- SSRF 防护：禁止 localhost/内网/链路本地地址。
- MVP 使用 API Key 鉴权，后续可升级为账号体系。
- 命令白名单 + 严格参数校验。
- 资源上限：最大深度、最大页面数、超时、重试次数。
- 生产环境禁止调试模式、开放跨域需白名单控制、敏感配置走环境变量。

### 2.9 验收标准
- 可通过网页输入 URL 并创建任务。
- 可通过命令控制任务生命周期。
- 页面可实时看到待爬取/已爬取/失败列表。
- 可查看清洗前后数据对照。
- 可导出 JSON/CSV。
- 全流程日志可在网页查看。
- 项目可部署到服务器并由外部用户访问。

---

## 3. 技术设计文档（TDD）

### 3.1 总体架构
- 前端：网页控制台 + 实时看板。
- 后端 API：鉴权、校验、命令解析、查询接口。
- 调度执行层：任务管理、队列引擎、爬虫 Worker、清洗 Worker。
- 存储层：任务/队列/原始数据/清洗数据/日志。
- 实时通道：WebSocket（优先）或 SSE。
- 部署层：Nginx 反向代理 + 应用进程管理 + 数据库/缓存服务。

### 3.2 建议技术栈
- 后端：Python + FastAPI。
- 异步任务：Celery + Redis（MVP 可先用进程内队列）。
- 数据库：PostgreSQL（SQLite 仅用于本地原型）。
- 前端：MVP 当前使用 FastAPI 挂载的原生 HTML/CSS/JavaScript 控制台，后续可升级为 React。
- 实时推送：MVP 当前使用 SSE，后续可升级为 WebSocket。
- 部署：Linux 云服务器 + systemd/Supervisor + Nginx。

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
  - 出参：同步附件下载响应
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
- `id`、`task_id`、`url`、`state`、`hop_count`、`retry_count`、`priority`
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

### 3.10 实施排期
- Day 1-2：表结构 + 状态机 + `/submit` + `/tasks`
- Day 3-4：命令引擎 + `/command`
- Day 5-6：爬虫 Worker + 队列执行
- Day 7-8：清洗 Worker + 去重
- Day 9：实时事件流
- Day 10：前端联调
- Day 11：导出 + 审计日志
- Day 12-14：测试、压测、上线准备
- Day 15+：服务器部署、域名接入、生产监控、备份与运维

### 3.11 部署要求
- 开发环境允许 SQLite，本地单进程运行。
- 预生产/生产环境切换为 PostgreSQL。
- 若引入 Celery，则需要 Redis 作为 Broker/Result Backend。
- 使用 Nginx 暴露 80/443，并反向代理到 FastAPI 服务。
- 使用 `systemd`、`supervisor` 或容器编排保证服务常驻。
- 配置 HTTPS、日志轮转、跨域策略、环境变量和密钥管理。

### 3.12 测试方案
- 单元测试：命令解析、状态迁移、清洗规则。
- 集成测试：提交 -> 抓取 -> 清洗 -> 导出全链路。
- 安全测试：SSRF、命令注入、限流。
- 性能测试：100 URL 任务负载与实时更新稳定性。

---

## 4. 当前进度确认

截至当前仓库状态，项目已经完成 Day 1-11 的 MVP 原型能力。

### 4.1 已完成

Day 1-2：
- SQLite 表结构初始化
- 任务状态机定义
- `POST /v1/crawl/submit`
- `GET /v1/tasks`
- `GET /v1/tasks/{task_id}`
- `GET /v1/health`
- URL 基础校验与 SSRF 初步防护

Day 3-4：
- 命令引擎基础实现
- `POST /v1/command`
- 已支持命令：
  - `help`
  - `crawl start`
  - `crawl pause`
  - `crawl resume`
  - `crawl stop`
  - `task status`
  - `queue list`
- 命令审计日志 `command_logs`
- 任务状态迁移事件写入 `event_logs`

Day 5-6：
- 进程内队列 Worker 已接入
- `running` 任务会自动消费 `pending` 队列项
- 抓取成功/失败会更新 `queue_items`、任务计数与 `event_logs`
- 支持基于页面链接继续入队，受 `limit` 与 `depth` 控制
- 新增 `GET /v1/tasks/{task_id}/queue`

Day 7-8：
- 抓取结果会落到 `raw_items`
- 已支持 `clean run task_id=<...>` 清洗命令
- 清洗阶段会规范化标题、内容、日期，并按 `news_id` / `title+date` 去重
- 已支持 `GET /v1/tasks/{task_id}/results?view=raw|clean`
- 任务详情中的 `clean_done_count` 会随清洗结果更新

Day 9：
- 已支持 `GET /v1/events/stream?task_id=...&after_id=...`
- 事件流采用 SSE，支持历史事件回放与 `after_id` 增量续传
- 任务结束后会短暂等待尾部事件，再自动关闭流
- 不存在的 `task_id` 会返回标准 `404` 错误载荷

Day 10：
- 已提供网页控制台首页 `/`
- 前端通过同源 API 调用 `submit`、`command`、`tasks`、`results`、`events/stream`
- 页面已支持任务选择、快捷命令、详情展示、实时事件流和导出按钮

Day 11：
- 已支持 `POST /v1/tasks/{task_id}/export`
- 可将 `clean_items` 同步导出为 `JSON` 或 `CSV` 附件
- 已补充导出接口与静态页面路由测试

Day 12-13：
- 已支持中文站点编码识别修复
- 已支持词云图生成接口与前端预览
- 已支持 `renderer=http|browser` 的任务级抓取模式
- `browser` 模式基于 Playwright 做动态页面渲染，不包含 `stealth.js` 或规避检测逻辑

### 4.2 当前未完成

- 生产环境的 Nginx/HTTPS 终态接入与域名发布
- Celery 任务细粒度拆分与更完整重试/死信策略
- 告警渠道（邮件/企业微信/Slack）对接
- 账号体系的权限分层（RBAC）与审计策略
- Playwright 运行依赖的安装引导与运行期环境探测优化

### 4.3 本轮已补充

- 已支持基于环境变量的运行配置读取
- 已支持可选启用的 API Key 鉴权
- 已支持队列分页与按状态汇总计数
- 已补齐前端结果表分页、队列分页和 API Key 输入态
- 已重做控制台界面，提升整体视觉与操作流
- 已修复 Edge 下的部分排布稳定性问题，并优化前端实时刷新策略与渲染开销，提升页面流畅度
- 已让 `PYMS_DB_URL` 真实参与数据库初始化（支持 `sqlite:///...` 与 `postgresql://...`）
- 已支持 `PYMS_QUEUE_BACKEND=inprocess|external|celery`
- 已新增 `worker_main.py` 用于独立队列 worker 进程启动
- 已新增 Celery 调度链路：`app/celery_app.py`、`app/celery_tasks.py`、`celery worker`、`celery beat`
- 已补充 Celery 细粒度调度策略：`批调度 + 单项任务`，支持可配置限流
- 已补充队列失败退避重试与死信落表：`dead_letters`
- 已新增运行环境探测与监控接口：`/v1/runtime/probe`、`/v1/metrics`
- 已补充 Prometheus + Alertmanager + Docker Compose 生产部署模板
- 已接入用户注册 / 登录 / 会话体系：`/v1/auth/register`、`/v1/auth/login`、`/v1/auth/logout`、`/v1/auth/me`
- 已接入 RBAC 与审计能力：`viewer/operator/admin`、`/v1/auth/users`、`/v1/auth/users/{id}/role`、`/v1/audit/logs`

### 4.4 当前结论

现在的仓库已经从“本地原型 MVP”升级为“可部署版基础形态”：支持 PostgreSQL/Redis、Celery worker/beat、会话鉴权和监控探针。

要达到最终目标，下一阶段必须继续完成：
1. Nginx / HTTPS / 域名与公网发布。
2. Celery 任务策略深化（细粒度任务、死信、限流、退避）。
3. 鉴权权限分层（RBAC）与生产审计闭环。

### 4.5 本次推进结果（2026-04-13）

- 已完成第 2 项：Celery 批调度 + 单项任务、失败退避重试、`dead_letters` 死信落表、可配置限流。
- 已完成第 3 项（告警渠道）：Alertmanager 模板支持邮件 / 企业微信 / Slack，并通过环境变量注入。
- 已完成第 4 项（权限与审计）：`viewer/operator/admin` RBAC、用户角色管理接口、`/v1/audit/logs` 审计查询。

---

## 5. 本地启动

### 5.1 环境变量

可选环境变量：

- `PYMS_APP_ENV`：运行环境标识，默认 `development`
- `PYMS_HOST`：监听地址，默认 `127.0.0.1`
- `PYMS_PORT`：监听端口，默认 `8000`
- `PYMS_API_KEY`：启用后，所有 `/v1/*` 业务接口需要 API Key
- `PYMS_AUTH_ENABLED`：是否启用注册/登录/会话鉴权，默认 `false`
- `PYMS_SESSION_TTL_HOURS`：会话有效期（小时），默认 `24`
- `PYMS_DB_URL`：数据库连接串，默认 `sqlite:///data/app.db`，部署建议 `postgresql://...`
- `PYMS_REDIS_URL`：当前用于声明目标 Redis 连接串，默认 `redis://127.0.0.1:6379/0`
- `PYMS_QUEUE_BACKEND`：队列运行模式，`inprocess`（默认）/`external`（手工 worker）/`celery`（生产建议）
- `PYMS_QUEUE_BATCH_SIZE`：Celery 单次处理的最大队列项数量，默认 `20`
- `PYMS_QUEUE_POLL_INTERVAL_SECONDS`：Celery beat 调度间隔秒数，默认 `2`
- `PYMS_QUEUE_RETRY_MAX_ATTEMPTS`：单队列项最大重试次数（不含首次），默认 `2`
- `PYMS_QUEUE_RETRY_BACKOFF_BASE_SECONDS`：重试基础退避秒数，默认 `0.5`
- `PYMS_QUEUE_RETRY_BACKOFF_MAX_SECONDS`：重试最大退避秒数，默认 `8`
- `PYMS_CELERY_QUEUE_DRAIN_RATE_LIMIT`：批调度任务限流（如 `5/s`），默认不限制
- `PYMS_CELERY_ITEM_RATE_LIMIT`：单项消费任务限流（如 `20/s`），默认不限制
- `PYMS_QUEUE_PAGE_SIZE`：队列接口默认分页大小
- `PYMS_QUEUE_PAGE_SIZE_MAX`：队列接口最大分页大小
- `PYMS_RESULT_PAGE_SIZE`：结果接口默认分页大小
- `PYMS_RESULT_PAGE_SIZE_MAX`：结果接口最大分页大小
- `PYMS_AUDIT_LOG_ENABLED`：是否启用审计日志，默认 `true`

PowerShell 示例：

```powershell
$env:PYMS_API_KEY="replace-with-real-key"
$env:PYMS_PORT="8000"
```

```powershell
& .\myvenv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

如果要切换为“API + 独立 worker”运行形态（不使用 Celery）：

```powershell
$env:PYMS_QUEUE_BACKEND="external"
python main.py
```

另开一个终端启动 worker：

```powershell
$env:PYMS_QUEUE_BACKEND="external"
python worker_main.py
```

如果要启用 Celery + Redis：

```powershell
$env:PYMS_QUEUE_BACKEND="celery"
$env:PYMS_REDIS_URL="redis://127.0.0.1:6379/0"
python main.py
```

另开两个终端启动 worker/beat：

```powershell
$env:PYMS_QUEUE_BACKEND="celery"
$env:PYMS_REDIS_URL="redis://127.0.0.1:6379/0"
celery -A app.celery_app:celery_app worker --loglevel=INFO
celery -A app.celery_app:celery_app beat --loglevel=INFO
```

如果要使用动态页面渲染模式，还需要额外安装 Playwright 浏览器：

```powershell
python -m playwright install chromium
```

默认监听：

```text
http://127.0.0.1:8000
```

浏览器入口：

```text
http://127.0.0.1:8000/
```

---

## 6. 快速验证

### 6.1 提交任务

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/v1/crawl/submit `
  -Headers @{Authorization="Bearer replace-with-real-key"} `
  -ContentType "application/json" `
  -Body '{"url":"https://example.com/news","limit":10,"depth":1,"renderer":"http"}'
```

### 6.2 查询任务列表

```powershell
Invoke-RestMethod `
  -Uri http://127.0.0.1:8000/v1/tasks `
  -Headers @{Authorization="Bearer replace-with-real-key"}
```

### 6.3 发送命令

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/v1/command `
  -Headers @{Authorization="Bearer replace-with-real-key"} `
  -ContentType "application/json" `
  -Body '{"command":"crawl start url=https://example.com/news limit=10 depth=1 renderer=browser","request_id":"req_manual_001"}'
```

### 6.4 查询单个任务

```powershell
Invoke-RestMethod `
  -Uri http://127.0.0.1:8000/v1/tasks/<task_id> `
  -Headers @{Authorization="Bearer replace-with-real-key"}
```

### 6.5 订阅事件流

```powershell
Invoke-WebRequest `
  -Uri "http://127.0.0.1:8000/v1/events/stream?task_id=<task_id>&after_id=0&api_key=replace-with-real-key" `
  -Headers @{Accept="text/event-stream"}
```

### 6.6 导出清洗结果

```powershell
Invoke-WebRequest `
  -Method Post `
  -Uri http://127.0.0.1:8000/v1/tasks/<task_id>/export `
  -Headers @{Authorization="Bearer replace-with-real-key"} `
  -ContentType "application/json" `
  -Body '{"format":"csv"}' `
  -OutFile .\clean_results.csv
```

### 6.7 打开网页控制台

直接访问：

```text
http://127.0.0.1:8000/
```

### 6.8 生成词云图

```powershell
Invoke-WebRequest `
  -Method Post `
  -Uri http://127.0.0.1:8000/v1/tasks/<task_id>/wordcloud `
  -Headers @{Authorization="Bearer replace-with-real-key"} `
  -ContentType "application/json" `
  -Body '{"view":"auto","width":1200,"height":720,"top_n":80}' `
  -OutFile .\task_wordcloud.png
```

---

## 7. 测试

当前已覆盖：
- Day 1-2 基础用例
- Day 3-4 命令引擎与 `/v1/command`
- Day 5-6 队列消费、抓取成功/失败、暂停恢复
- Day 7-8 原始结果落库、清洗去重、结果查询
- Day 9 事件流回放、`after_id` 增量订阅、未知任务错误返回
- Day 10 导出接口成功/失败路径
- Day 11 首页与静态资源可访问性
- Day 12 中文编码识别修复
- Day 13 词云图接口与回退逻辑
- Day 14 `renderer=browser` 任务配置与 worker 分发
- Day 15 API Key 鉴权与队列分页响应结构
- Day 16 会话鉴权（注册/登录/会话校验）

执行方式：

```powershell
python -m unittest discover -s tests -p "test_day1_day2.py" -v
python -m unittest discover -s tests -p "test_day3_day4.py" -v
python -m unittest discover -s tests -p "test_day5_day6.py" -v
python -m unittest discover -s tests -p "test_day7_day8.py" -v
python -m unittest discover -s tests -p "test_day9.py" -v
python -m unittest discover -s tests -p "test_day10.py" -v
python -m unittest discover -s tests -p "test_day11.py" -v
python -m unittest discover -s tests -p "test_day12.py" -v
python -m unittest discover -s tests -p "test_day13.py" -v
python -m unittest discover -s tests -p "test_*.py" -v
```

---

## 8. 后续建议

建议按下面顺序推进：

1. 在 `deploy/docker-compose.prod.yml` 基础上补 Nginx + HTTPS + 域名接入。
2. 对 Celery 增加失败重试分级、死信队列与限流配置。
3. 将 Alertmanager 默认接收器替换为真实告警渠道。
4. 在当前会话鉴权基础上补 RBAC 与操作审计。

---

## 9. 部署与监控

已提供以下部署资源：

- `Dockerfile`
- `deploy/docker-compose.prod.yml`
- `deploy/monitoring/prometheus.yml`
- `deploy/monitoring/alert_rules.yml`
- `deploy/monitoring/alertmanager.yml`
- `scripts/deploy.ps1`
- `scripts/probe_runtime.ps1`

生产启动示例：

```powershell
Copy-Item .env.production.example .env.production
# 修改 .env.production 中密码和密钥后执行
.\scripts\deploy.ps1 -Action up
```

运行探测：

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/v1/runtime/probe
Invoke-WebRequest -Uri http://127.0.0.1:8000/v1/metrics
```

---

## 10. 相关文档

- [API_SPEC.md](./API_SPEC.md)
- [DATABASE_DDL.sql](./DATABASE_DDL.sql)
- [WIREFRAME.md](./WIREFRAME.md)

---

## 11. 本机运行库补齐记录（2026-04-12）

已补齐：

- 系统 Python 已安装 `psycopg-binary==3.3.3`，`psycopg` 导入正常。
- `myvenv` 中 `psycopg / psycopg-binary / celery / redis / playwright` 导入正常。
- 已执行 `playwright install chromium`（在当前环境可执行）。
- 已安装 PostgreSQL 16（服务：`postgresql-x64-16`，状态 `Running`）。
- 已安装 Redis on Windows（服务：`Redis`，状态 `Running`）。

已发现并处理：

- `Memurai Developer` 安装失败（错误 `1603`，安装日志显示 `MsiSystemRebootPending=1` 与临时目录权限错误），因此改用 `Redis.Redis` 包完成 Redis 服务安装。
- `psql.exe` 安装路径为 `C:\Program Files\PostgreSQL\16\bin\psql.exe`，若新终端未识别命令，请重新打开终端后再执行。
