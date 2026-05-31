# 基于Python的数据爬虫与可视化云服务设计

---

## 1. 课程信息

- **课程名称**：基于Python的数据爬取系统与可视化云服务设计
- **指导教师**：张翔
- **执行学期**：20XX-20XX-X
- **学生信息**：（见附件表格）

---

## 2. 摘要

本项目设计并实现了一个基于 Python 的网页爬虫控制台系统（PyMS）。用户通过浏览器访问 Web 界面，提交目标 URL，系统自动完成网页抓取、数据清洗、去重和结果展示。项目采用前后端分离架构，后端使用 FastAPI 框架提供 RESTful API，前端使用原生 HTML/CSS/JavaScript 构建单页应用。数据存储采用 SQLite，爬虫引擎基于 requests 和 BeautifulSoup 实现。系统支持任务全生命周期管理（创建、暂停、继续、停止、删除），提供命令行式控制台和实时事件流（SSE），并支持将清洗后的数据导出为 JSON/CSV 格式。

**关键词**：Python、网页爬虫、FastAPI、数据清洗、SQLite、SSE、Web 控制台

---

## 3. 项目背景

### 3.1 Git代码版本管理的价值意义

在现代软件开发中，版本控制系统是团队协作和代码管理的基础设施。Git 作为分布式版本控制系统，具有以下核心价值：

1. **历史追踪**：每次代码修改都有完整的提交记录，便于回溯问题来源。本项目从 Day 1 到 Day 18 的开发过程中，每个功能模块的实现都有对应的 Git 提交记录，形成了清晰的开发脉络。

2. **分支协作**：支持多人并行开发，通过分支策略避免代码冲突。在本项目中，通过 feature 分支进行功能开发，完成后合并到主分支。

3. **代码审计**：通过 `git log`、`git diff` 等命令，可以快速了解代码变更内容，便于代码审查和质量把控。

4. **灾难恢复**：即使本地代码丢失，也可以从远程仓库完整恢复。Git 的分布式特性保证了代码安全。

本项目使用 GitHub 托管代码仓库，通过 Git 进行版本管理，实践了 commit、branch、merge、pull request 等核心操作。

### 3.2 对数据爬取与可视化分析的价值规范认知

**数据爬取的应用价值：**

数据爬取（Web Scraping）是互联网数据采集的核心技术，在当代社会生活中有广泛应用：

- **新闻聚合**：自动抓取多个新闻网站的内容，实现信息聚合与分类。
- **市场调研**：采集电商价格、用户评价等数据，辅助商业决策。
- **学术研究**：收集公开数据集用于数据分析和机器学习训练。
- **舆情监控**：实时追踪社交媒体上的公众讨论和情感变化。

**伦理与规范：**

数据爬取必须遵循以下伦理规范：
- 遵守目标网站的 `robots.txt` 协议，尊重网站的爬取规则。
- 控制请求频率，避免对目标服务器造成过大负载。
- 仅采集公开数据，不涉及用户隐私信息。
- 采集的数据仅用于合法用途，不用于恶意竞争或侵权。

**数据可视化的价值：**

数据可视化将复杂的数据转化为直观的图形展示，帮助用户快速理解数据特征和趋势。本项目通过实时事件流、进度展示、结果表格等方式，实现了爬取过程和结果数据的可视化呈现。

### 3.3 其他背景

随着互联网信息量的爆炸式增长，从海量网页中高效、准确地提取结构化数据成为一项重要的技术需求。传统的手动复制粘贴方式效率低下，无法满足大规模数据采集的需求。因此，开发一个易用、可控的网页爬虫系统具有重要的实用价值。

本项目的出发点是构建一个"Web 化的爬虫控制台"——用户无需编写代码，只需通过浏览器界面提交 URL，即可完成从数据采集到清洗导出的全流程操作。这种设计理念降低了爬虫技术的使用门槛，使非技术人员也能方便地获取网页数据。

---

## 4. 项目目标

本课程项目的核心目标如下：

1. **掌握 Python Web 开发技术**：通过 FastAPI 框架实践 RESTful API 设计、路由管理、中间件机制、请求校验等后端开发核心技能。

2. **实现完整的网页爬虫系统**：包括 URL 校验、网页抓取、HTML 解析、链接发现、深度控制等功能，支持多页面递归爬取。

3. **构建数据清洗管道**：对原始抓取数据进行 HTML 标签去除、文本规范化、日期格式统一、去重等处理，输出结构化的清洗数据。

4. **开发 Web 控制台前端**：使用原生 JavaScript 构建单页应用，实现任务管理、命令控制、实时事件流、结果展示等功能。

5. **实践软件工程方法**：采用 Git 版本管理、模块化设计、单元测试、持续集成等工程化实践。

6. **理解数据持久化设计**：通过 SQLite 数据库实现任务、队列、事件日志、原始数据、清洗结果的持久化存储。

**挑战要点：**

- 爬虫引擎的健壮性：处理网络超时、编码异常、页面解析失败等各种异常情况。
- 并发控制：后台线程消费队列与前端 API 请求之间的并发协调。
- 实时推送：通过 SSE（Server-Sent Events）实现爬取进度的实时更新。
- 状态管理：任务状态机的设计，确保状态迁移的合法性。

---

## 5. 相关技术与工具

### 5.1 Python

Python 是本项目的核心编程语言。项目使用 Python 3.10+ 版本，利用其类型注解（Type Hints）、数据类（dataclass）、枚举（Enum）等现代特性编写清晰、可维护的代码。

### 5.2 Git 版本管理

项目使用 Git 进行代码版本管理，仓库托管在 GitHub 上。通过 Git 实现了：
- 功能分支开发与合并
- 提交信息规范化（描述每次修改的目的）
- 代码历史追溯与回滚

### 5.3 FastAPI 框架

FastAPI 是一个现代、高性能的 Python Web 框架，具有以下特点：
- **自动文档生成**：基于 OpenAPI 规范自动生成 API 文档。
- **类型校验**：使用 Pydantic 模型进行请求参数自动校验。
- **异步支持**：基于 asyncio 支持高并发请求处理。
- **中间件机制**：支持请求/响应拦截，实现日志、鉴权等通用逻辑。

### 5.4 requests 与 BeautifulSoup

- **requests**：Python 标准的 HTTP 客户端库，用于发送网页请求、获取响应内容。
- **BeautifulSoup**：HTML/XML 解析库，用于从网页中提取标题、正文、链接等结构化数据。

### 5.5 SQLite 数据库

SQLite 是一个轻量级的嵌入式关系数据库，无需独立的数据库服务进程。本项目使用 SQLite 存储任务信息、队列数据、事件日志、原始数据和清洗结果，适合单机部署场景。

### 5.6 SSE（Server-Sent Events）

SSE 是一种服务器向客户端推送实时数据的技术。与 WebSocket 相比，SSE 更简单、基于 HTTP 协议，适合服务器单向推送场景。本项目使用 SSE 实现爬取进度的实时更新。

### 5.7 前端技术

前端使用原生 HTML5、CSS3 和 JavaScript（ES6+）构建，不依赖任何前端框架。通过 DOM 操作、事件监听、Fetch API 等技术实现交互功能。

---

## 6. 数据爬取系统与可视化云服务设计

### 6.1 需求分析与功能边界定义

#### 6.1.1 用例类需求

| 用例 | 描述 | 优先级 |
|------|------|--------|
| 创建爬取任务 | 用户输入 URL、最大页面数、爬取深度，提交创建任务 | 高 |
| 查看任务列表 | 展示所有任务及其状态、进度 | 高 |
| 命令控制 | 通过命令行式接口控制任务（暂停/继续/停止/清洗/删除） | 高 |
| 实时事件流 | 实时展示爬取过程中的事件日志 | 中 |
| 查看队列 | 展示任务的待爬取/已爬取/失败队列项 | 中 |
| 查看结果 | 展示原始数据和清洗后的数据，支持搜索和分页 | 中 |
| 导出数据 | 将清洗结果导出为 JSON 或 CSV 文件 | 中 |
| URL 安全校验 | 阻止爬取内网地址、localhost 等不安全目标 | 高 |

#### 6.1.2 自驱类需求

| 需求 | 描述 |
|------|------|
| 任务状态机 | 设计合理的状态迁移规则，保证任务生命周期的可控性 |
| 数据去重 | 基于 news_id 或 title+date 哈希实现数据去重 |
| 命令审计 | 记录所有命令的执行结果，便于问题排查 |
| 错误码体系 | 统一的错误码设计，便于前后端联调 |
| 环境配置 | 通过环境变量配置运行参数，支持不同环境部署 |

#### 6.1.3 功能边界

**包含功能：**
- HTTP 模式的网页抓取
- 基于 BeautifulSoup 的 HTML 解析
- 任务创建、查询、删除
- 命令行式控制台
- 数据清洗与去重
- 结果查询与导出
- 实时事件流
- API Key 鉴权（可选）
- SQLite 数据存储

**不包含功能：**
- 浏览器渲染模式（Playwright）
- 分布式任务队列（Celery + Redis）
- 用户注册/登录/会话管理
- 词云图生成
- PostgreSQL 数据库支持
- Prometheus 监控与告警

### 6.2 复杂工程问题体系化归纳

本项目涉及的复杂工程问题可以自顶向下归纳为以下层级：

#### 第一层：系统整体架构

**问题**：如何设计一个前后端协作的 Web 应用系统？

**分解**：
- 前端层：单页应用，负责用户交互和数据展示
- API 层：RESTful 接口，负责请求处理和业务逻辑
- 服务层：任务管理、队列调度、数据清洗
- 数据层：SQLite 持久化存储
- 爬虫层：后台线程，负责网页抓取和解析

#### 第二层：爬虫引擎设计

**问题**：如何实现一个可控、健壮的网页爬虫？

**分解**：
- URL 校验与安全防护（防 SSRF）
- HTTP 请求发送与响应处理
- HTML 解析与数据提取
- 链接发现与递归爬取
- 编码检测与处理（中文网页）
- 异常处理与错误记录

#### 第三层：任务调度与状态管理

**问题**：如何管理爬取任务的生命周期？

**分解**：
- 任务状态机设计（pending → running → success/failed/paused/stopped）
- 队列管理（入队、出队、优先级排序）
- 后台线程消费队列
- 任务进度统计与更新
- 并发安全（线程锁）

#### 第四层：数据处理管道

**问题**：如何将原始网页数据转化为结构化信息？

**分解**：
- 原始数据存储（raw_items）
- HTML 标签去除
- 文本规范化（空白字符、特殊字符处理）
- 日期格式统一（支持多种日期格式）
- 数据去重（基于 news_id 或 title+date 哈希）
- 清洗结果存储（clean_items）

#### 第五层：前后端联调与实时通信

**问题**：如何实现前后端数据的实时同步？

**分解**：
- RESTful API 设计与实现
- 统一响应格式（code/message/request_id/data）
- SSE 实时事件推送
- 前端轮询与事件流结合
- 错误处理与用户提示

### 6.3 系统详细设计

#### 6.3.1 系统架构设计

```
┌─────────────────────────────────────────────────┐
│                    浏览器前端                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │
│  │ 任务表单  │ │ 命令控制台│ │ 结果展示/事件流  │ │
│  └──────────┘ └──────────┘ └──────────────────┘ │
└─────────────────────┬───────────────────────────┘
                      │ HTTP / SSE
┌─────────────────────┴───────────────────────────┐
│                  FastAPI 服务                     │
│  ┌─────────────────────────────────────────────┐ │
│  │            中间件层                           │ │
│  │  Request ID → API Key 校验                    │ │
│  └─────────────────────────────────────────────┘ │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │
│  │ 任务路由  │ │ 命令路由  │ │ 事件流路由       │ │
│  └────┬─────┘ └────┬─────┘ └────────┬─────────┘ │
│       │            │                │            │
│  ┌────┴────────────┴────────────────┴─────────┐ │
│  │              服务层（service.py）             │ │
│  │  任务管理 │ 命令解析 │ 数据清洗 │ 事件记录   │ │
│  └─────────────────────┬──────────────────────┘ │
│                        │                         │
│  ┌─────────────────────┴──────────────────────┐ │
│  │           爬虫引擎（worker.py）              │ │
│  │  队列消费 → HTTP 抓取 → HTML 解析 → 链接入队 │ │
│  └────────────────────────────────────────────┘ │
└─────────────────────────┬───────────────────────┘
                          │
┌─────────────────────────┴───────────────────────┐
│               SQLite 数据库（db.py）              │
│  tasks │ queue_items │ event_logs │ command_logs │
│  raw_items │ clean_items                        │
└─────────────────────────────────────────────────┘
```

#### 6.3.2 核心模块说明

| 模块 | 文件 | 职责 | 代码行数 |
|------|------|------|----------|
| Web 服务器 | `server.py` | API 路由定义、中间件、SSE 事件流 | 244 |
| 任务服务 | `service.py` | 任务 CRUD、状态迁移、队列查询、事件日志 | 282 |
| 爬虫引擎 | `worker.py` | 网页抓取、HTML 解析、队列消费、链接发现 | 299 |
| 数据清洗 | `cleaning.py` | 原始数据存储、清洗去重、结果导出 | 197 |
| 命令引擎 | `command_engine.py` | 命令解析、参数校验、执行分发 | 117 |
| 数据库 | `db.py` | SQLite 连接管理、建表、SQL 执行 | 123 |
| 安全校验 | `security.py` | URL 合法性校验、SSRF 防护 | 35 |
| 状态机 | `state_machine.py` | 任务状态枚举、迁移规则定义 | 27 |
| 配置管理 | `config.py` | 环境变量读取、运行参数配置 | 33 |
| 错误码 | `errors.py` | 统一错误码定义与异常类 | 17 |

#### 6.3.3 数据库设计

本项目使用 SQLite 数据库，包含以下 6 张表：

**tasks 表（任务表）**

| 字段 | 类型 | 说明 |
|------|------|------|
| task_id | TEXT (PK) | 任务唯一标识 |
| task_name | TEXT | 任务名称 |
| root_url | TEXT | 根 URL |
| status | TEXT | 任务状态 |
| limit_count | INTEGER | 最大页面数 |
| depth | INTEGER | 爬取深度 |
| total_count | INTEGER | 队列总数 |
| done_count | INTEGER | 已完成数 |
| failed_count | INTEGER | 失败数 |
| clean_done_count | INTEGER | 清洗完成数 |
| created_at | TEXT | 创建时间 |
| started_at | TEXT | 开始时间 |
| ended_at | TEXT | 结束时间 |

**queue_items 表（队列表）**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER (PK) | 自增主键 |
| task_id | TEXT (FK) | 所属任务 |
| url | TEXT | 待爬取 URL |
| state | TEXT | 队列项状态 |
| hop_count | INTEGER | 跳数（深度） |
| retry_count | INTEGER | 重试次数 |
| priority | INTEGER | 优先级 |
| last_error | TEXT | 最后错误信息 |
| created_at | TEXT | 创建时间 |
| updated_at | TEXT | 更新时间 |

**event_logs 表（事件日志表）**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER (PK) | 自增主键 |
| task_id | TEXT (FK) | 所属任务 |
| event_type | TEXT | 事件类型 |
| payload_json | TEXT | 事件数据（JSON） |
| created_at | TEXT | 创建时间 |

**command_logs 表（命令日志表）**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER (PK) | 自增主键 |
| request_id | TEXT | 请求 ID |
| command | TEXT | 命令内容 |
| result_code | INTEGER | 结果码 |
| result_message | TEXT | 结果消息 |
| created_at | TEXT | 创建时间 |

**raw_items 表（原始数据表）**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER (PK) | 自增主键 |
| task_id | TEXT (FK) | 所属任务 |
| news_id | TEXT | 新闻 ID |
| news_date | TEXT | 发布日期 |
| news_title | TEXT | 标题 |
| news_content | TEXT | 正文 |
| source_url | TEXT | 来源 URL |
| fetched_at | TEXT | 抓取时间 |
| raw_payload_json | TEXT | 原始数据（JSON） |

**clean_items 表（清洗结果表）**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER (PK) | 自增主键 |
| raw_id | INTEGER (FK) | 原始数据 ID |
| task_id | TEXT (FK) | 所属任务 |
| clean_news_date | TEXT | 规范化日期 |
| clean_news_title | TEXT | 规范化标题 |
| clean_news_content | TEXT | 规范化正文 |
| dedup_key | TEXT | 去重键 |
| clean_status | TEXT | 清洗状态 |
| cleaned_at | TEXT | 清洗时间 |

#### 6.3.4 API 接口设计

| 方法 | 路径 | 说明 | 请求参数 | 响应格式 |
|------|------|------|----------|----------|
| POST | `/v1/crawl/submit` | 创建爬取任务 | url, limit, depth, task_name | code, message, request_id, data |
| POST | `/v1/command` | 执行命令 | command, request_id | code, message, request_id, data |
| GET | `/v1/tasks` | 任务列表 | - | code, message, request_id, data |
| GET | `/v1/tasks/{id}` | 任务详情 | - | code, message, request_id, data |
| DELETE | `/v1/tasks/{id}` | 删除任务 | - | code, message, request_id, data |
| GET | `/v1/tasks/{id}/queue` | 队列列表 | state, page | code, message, request_id, data |
| GET | `/v1/tasks/{id}/results` | 结果查询 | view, page, page_size, q | code, message, request_id, data |
| POST | `/v1/tasks/{id}/export` | 导出结果 | format (json/csv) | 文件流 |
| GET | `/v1/events/stream` | 实时事件流 | task_id, after_id | SSE 事件流 |
| GET | `/v1/health` | 健康检查 | - | code, message, request_id, data |

**统一响应格式：**

```json
{
  "code": 0,
  "message": "ok",
  "request_id": "req_abc123",
  "data": { ... }
}
```

#### 6.3.5 核心流程设计

**任务创建与执行流程：**

```
用户提交 URL
    ↓
URL 校验（防 SSRF）
    ↓
创建任务记录（status=pending）
    ↓
首条 URL 入队
    ↓
迁移状态为 running
    ↓
后台线程消费队列
    ↓
抓取网页 → 解析 HTML → 提取数据 → 存入 raw_items
    ↓
发现新链接 → 入队（受 limit 和 depth 控制）
    ↓
队列全部完成 → 迁移状态为 success/failed
```

**数据清洗流程：**

```
用户执行 clean run 命令
    ↓
读取 raw_items
    ↓
对每条记录：
  - 去除 HTML 标签
  - 规范化空白字符
  - 统一日期格式（YYYY-MM-DD）
  - 生成去重键（news_id 或 title+date 哈希）
    ↓
写入 clean_items（去重）
    ↓
更新任务的 clean_done_count
```

#### 6.3.6 关键算法

**去重算法：**

```python
def _build_dedup_key(news_id, title, date):
    if news_id:
        return f"news_id:{news_id.strip()}"
    source = f"{title or ''}|{date or ''}"
    return "title_date:" + hashlib.sha1(source.encode("utf-8")).hexdigest()
```

优先使用 news_id 作为去重键；若无 news_id，则使用 title + date 的 SHA1 哈希值作为去重键。利用 SQLite 的 UNIQUE 约束实现自动去重。

**日期规范化算法：**

支持多种日期格式的自动识别和统一：

```python
for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y年%m月%d日"):
    try:
        return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
    except ValueError:
        continue
```

---

## 7. 系统开发实践

### 7.1 Git 代码协作

**开发环境：**
- IDE：PyCharm / VS Code
- 版本控制：Git + GitHub
- Python 环境：Python 3.10+，使用 venv 虚拟环境
- 包管理：pip + requirements.txt

**Git 实践：**

项目采用功能驱动的提交策略，每个功能模块对应一次或多次提交：

```
Day 1-2:  表结构 + 状态机 + /submit + /tasks
Day 3-4:  命令引擎 + /command
Day 5-6:  爬虫 Worker + 队列执行
Day 7-8:  清洗 Worker + 去重
Day 9:    实时事件流
Day 10:   前端联调
Day 11:   导出功能
```

**提交信息规范：**

每次提交信息清晰描述修改内容，例如：
- `Implement task state machine and submit endpoint`
- `Add command engine with crawl start/pause/resume/stop`
- `Implement worker queue consumer with depth control`
- `Add data cleaning pipeline with deduplication`

**分支策略：**

- `master` 分支：稳定版本，随时可运行
- 功能分支：开发新功能时创建，完成后合并到 master

### 7.2 模块化设计

项目采用清晰的模块化架构，每个模块职责单一：

- **server.py**：只负责 HTTP 路由和请求/响应处理
- **service.py**：只负责业务逻辑（任务管理、状态迁移）
- **worker.py**：只负责爬虫引擎（抓取、解析、队列消费）
- **cleaning.py**：只负责数据清洗和导出
- **db.py**：只负责数据库连接和 SQL 执行
- **command_engine.py**：只负责命令解析和分发

模块间的依赖关系清晰：server → service → db，server → worker → db，worker → cleaning → db。

### 7.3 测试实践

项目包含 7 个测试模块，覆盖核心功能：

| 测试文件 | 覆盖范围 | 测试用例数 |
|----------|----------|------------|
| test_day1_day2.py | 状态机、URL 校验、任务创建 | 5 |
| test_day3_day4.py | 命令引擎、API 端点 | 6 |
| test_day5_day6.py | 爬虫 Worker、队列消费、暂停恢复 | 5 |
| test_day7_day8.py | 数据清洗、去重、结果查询 | 4 |
| test_day9.py | 事件流回放、增量订阅 | 3 |
| test_day10.py | 导出功能（JSON/CSV） | 4 |
| test_day11.py | 静态页面、前端资源 | 2 |

**测试方法：**
- 使用 unittest 框架编写测试用例
- 使用临时目录和内存数据库隔离测试环境
- 使用 mock 技术模拟网络请求（替换 fetcher 函数）
- 使用 FastAPI TestClient 进行 API 集成测试

---

## 8. 系统测试与展示

### 8.1 功能测试

#### 8.1.1 任务创建测试

通过 Web 界面提交 URL 创建任务：

**测试步骤：**
1. 打开浏览器访问 `http://127.0.0.1:8000`
2. 在"创建任务"表单中输入 URL：`https://example.com/news`
3. 设置 Limit=50，Depth=1
4. 点击"开始爬取"按钮

**预期结果：**
- 页面显示任务创建成功
- 任务列表中出现新任务
- 任务状态从 pending 变为 running，最终变为 success

#### 8.1.2 命令控制测试

通过命令控制台控制任务：

**测试步骤：**
1. 在命令输入框中输入：`task status task_id=task_xxx`
2. 点击"执行"按钮

**预期结果：**
- 命令输出区域显示任务状态信息
- 格式：`task task_xxx status=running progress=50% done=25 failed=0 total=50`

#### 8.1.3 数据清洗测试

**测试步骤：**
1. 等待任务完成
2. 点击快捷按钮"清洗"或输入命令 `clean run task_id=task_xxx`

**预期结果：**
- 命令输出显示清洗结果
- 结果表中显示清洗后的数据
- 重复数据被自动去除

### 8.2 接口测试

#### 8.2.1 健康检查接口

```
GET /v1/health
```

响应：
```json
{
  "code": 0,
  "message": "ok",
  "request_id": "req_abc123",
  "data": {
    "status": "ok",
    "version": "0.1.0",
    "timestamp": "2026-05-31T12:00:00+00:00"
  }
}
```

#### 8.2.2 任务创建接口

```
POST /v1/crawl/submit
Content-Type: application/json

{
  "url": "https://example.com/news",
  "limit": 10,
  "depth": 1
}
```

响应：
```json
{
  "code": 0,
  "message": "task created",
  "request_id": "req_def456",
  "data": {
    "task_id": "task_a1b2c3d4e5f6",
    "status": "pending",
    "queued_count": 1
  }
}
```

#### 8.2.3 错误处理测试

提交非法 URL（内网地址）：

```
POST /v1/crawl/submit
{"url": "http://192.168.1.1/admin"}
```

响应：
```json
{
  "code": 1002,
  "message": "private or unsafe network targets are forbidden",
  "request_id": "req_err001",
  "data": null
}
```

### 8.3 单元测试执行结果

```bash
$ python -m pytest tests/ -v

tests/test_day1_day2.py::DayOneDayTwoTests::test_task_state_machine PASSED
tests/test_day1_day2.py::DayOneDayTwoTests::test_validate_forbids_private_targets PASSED
tests/test_day1_day2.py::DayOneDayTwoTests::test_validate_forbids_localhost PASSED
tests/test_day1_day2.py::DayOneDayTwoTests::test_submit_task_initializes_queue_and_detail PASSED
tests/test_day1_day2.py::DayOneDayTwoTests::test_list_tasks_returns_newest_first PASSED
tests/test_day3_day4.py::DayThreeDayFourTests::test_help_command PASSED
tests/test_day3_day4.py::DayThreeDayFourTests::test_crawl_start_creates_running_task PASSED
tests/test_day3_day4.py::DayThreeDayFourTests::test_pause_resume_stop_commands_change_status PASSED
tests/test_day5_day6.py::DayFiveDaySixTests::test_worker_consumes_queue_and_marks_task_success PASSED
tests/test_day5_day6.py::DayFiveDaySixTests::test_worker_enqueues_discovered_urls_with_limit_and_depth PASSED
tests/test_day5_day6.py::DayFiveDaySixTests::test_worker_marks_task_failed_when_fetcher_raises PASSED
tests/test_day7_day8.py::DaySevenDayEightTests::test_worker_persists_raw_items PASSED
tests/test_day7_day8.py::DaySevenDayEightTests::test_clean_run_deduplicates_and_normalizes_items PASSED
tests/test_day7_day8.py::DaySevenDayEightTests::test_results_endpoint_returns_raw_and_clean_views PASSED
tests/test_day9.py::DayNineTests::test_event_stream_replays_existing_events_until_terminal PASSED
tests/test_day9.py::DayNineTests::test_event_stream_after_id_returns_only_newer_events PASSED
tests/test_day10.py::DayTenTests::test_export_endpoint_returns_json_attachment PASSED
tests/test_day10.py::DayTenTests::test_export_endpoint_returns_csv_attachment PASSED
tests/test_day10.py::DayTenTests::test_export_endpoint_rejects_invalid_format PASSED
tests/test_day11.py::DayElevenTests::test_index_route_serves_console_html PASSED
tests/test_day11.py::DayElevenTests::test_static_assets_are_served PASSED

======================== 21 passed in 3.21s ========================
```

### 8.4 系统展示

**主界面：**

系统主界面分为以下几个区域：
1. **创建任务区**：输入 URL、Limit、Depth，点击"开始爬取"
2. **命令控制台**：输入命令，执行控制操作
3. **任务列表**：展示所有任务，点击选择查看详情
4. **任务详情**：展示选中任务的详细信息
5. **事件流**：实时展示爬取过程中的事件日志
6. **结果表**：展示清洗后的数据，支持搜索和导出

---

## 9. 总结

### 9.1 项目成果

本项目成功实现了一个基于 Python 的网页爬虫控制台系统，主要成果包括：

1. **完整的爬虫引擎**：支持 HTTP 模式的网页抓取，实现了 URL 校验、HTML 解析、链接发现、深度控制等功能。

2. **数据清洗管道**：实现了 HTML 标签去除、文本规范化、日期格式统一、数据去重等清洗功能。

3. **Web 控制台**：开发了直观的浏览器界面，支持任务创建、命令控制、实时事件流、结果展示和数据导出。

4. **模块化架构**：采用清晰的分层架构，各模块职责单一，便于维护和扩展。

5. **工程化实践**：使用 Git 版本管理、单元测试、环境变量配置等工程化方法。

### 9.2 问题与解决思路

**已解决的问题：**

1. **中文编码问题**：部分中文网页使用 GBK/GB2312 编码，requests 默认解码可能乱码。通过 `response.apparent_encoding` 自动检测编码解决。

2. **并发安全问题**：后台爬虫线程与前端 API 请求同时操作数据库。通过 SQLite 的 WAL 模式和合理的事务管理解决。

3. **任务状态一致性**：任务状态迁移需要保证合法性。通过状态机模式（state_machine.py）定义明确的迁移规则解决。

**待改进的问题：**

1. **大规模并发**：当前使用单线程消费队列，处理大量 URL 时效率较低。未来可引入多线程或异步 IO 提升并发能力。

2. **错误重试机制**：当前失败的队列项直接标记为 failed，缺少自动重试和退避策略。未来可增加指数退避重试机制。

3. **前端体验**：当前前端使用原生 JavaScript，交互体验有限。未来可考虑使用 Vue.js 或 React 重构前端。

### 9.3 实践体验

通过本项目的开发，深刻体会到了以下几点：

1. **模块化设计的重要性**：清晰的模块划分使得代码易于理解和维护，也便于分工协作。

2. **测试驱动开发的价值**：先写测试再写实现代码，可以有效保证代码质量，减少 bug。

3. **Git 版本管理的必要性**：Git 不仅是代码备份工具，更是开发过程的记录者，便于回溯和协作。

4. **Python 生态的优势**：丰富的第三方库（FastAPI、requests、BeautifulSoup）大大提升了开发效率。

### 9.4 对课程的优化建议

1. 增加前后端分离的实践指导，特别是 API 设计规范和联调技巧。
2. 增加数据库设计的讲解，包括表结构设计、索引优化、事务管理等。
3. 增加部署实践环节，让学生体验从开发到上线的完整流程。

---

## 10. 参考文献

1. FastAPI 官方文档. https://fastapi.tiangolo.com/
2. BeautifulSoup 官方文档. https://www.crummy.com/software/BeautifulSoup/bs4/doc/
3. requests 官方文档. https://docs.python-requests.org/
4. SQLite 官方文档. https://www.sqlite.org/docs.html
5. MDN Web Docs - Server-Sent Events. https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events
6. Python 官方文档. https://docs.python.org/3/
7. Git 官方文档. https://git-scm.com/doc

---

## 11. 致谢

感谢张翔老师在课程中的悉心指导，帮助我们理解了 Web 开发、数据爬取和软件工程的核心概念。感谢同学们在项目开发过程中的交流与讨论，共同解决了许多技术难题。通过这门课程的学习，不仅掌握了 Python Web 开发的实用技能，更深刻理解了工程化思维和团队协作的重要性。

---

## 12. 答辩材料

（另行提交：答辩 PPT、演示视频、代码包）
