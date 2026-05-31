# PyMS 网页爬虫控制台

一个简单的网页爬虫应用。通过浏览器提交 URL，系统自动抓取网页、清洗数据、展示结果。

## 功能

- 输入 URL 创建爬取任务
- 命令行式控制台（开始/暂停/继续/停止/清洗/删除）
- 实时事件流显示爬取进度
- 数据清洗：去 HTML 标签、日期规范化、去重
- 结果导出为 JSON 或 CSV

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动服务
python main.py

# 3. 打开浏览器
# 访问 http://127.0.0.1:8000
```

## 项目结构

```
pyms/
├── main.py                 # 入口文件
├── requirements.txt        # 依赖（4个包）
├── app/
│   ├── server.py           # Web 路由（FastAPI）
│   ├── config.py           # 配置读取
│   ├── db.py               # SQLite 数据库
│   ├── service.py          # 任务管理
│   ├── command_engine.py   # 命令解析
│   ├── worker.py           # 爬虫 Worker
│   ├── cleaning.py         # 数据清洗
│   ├── security.py         # URL 安全校验
│   ├── state_machine.py    # 任务状态机
│   ├── errors.py           # 错误码
│   └── static/
│       ├── index.html      # 前端页面
│       ├── styles.css      # 样式
│       └── app.js          # 前端逻辑
└── tests/                  # 测试
```

## 支持的命令

| 命令 | 说明 |
|------|------|
| `help` | 显示帮助 |
| `crawl start url=<...> limit=<...> depth=<...>` | 创建并启动任务 |
| `crawl pause task_id=<...>` | 暂停任务 |
| `crawl resume task_id=<...>` | 继续任务 |
| `crawl stop task_id=<...>` | 停止任务 |
| `task status task_id=<...>` | 查看任务状态 |
| `task delete task_id=<...>` | 删除任务 |
| `queue list task_id=<...>` | 查看队列 |
| `clean run task_id=<...>` | 执行数据清洗 |

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/v1/crawl/submit` | 创建爬取任务 |
| POST | `/v1/command` | 执行命令 |
| GET | `/v1/tasks` | 任务列表 |
| GET | `/v1/tasks/{id}` | 任务详情 |
| DELETE | `/v1/tasks/{id}` | 删除任务 |
| GET | `/v1/tasks/{id}/queue` | 队列列表 |
| GET | `/v1/tasks/{id}/results` | 结果查询 |
| POST | `/v1/tasks/{id}/export` | 导出结果 |
| GET | `/v1/events/stream` | 实时事件流 |
| GET | `/v1/health` | 健康检查 |

## 运行测试

```bash
python -m pytest tests/ -v
```

## 环境变量（可选）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `PYMS_HOST` | `127.0.0.1` | 监听地址 |
| `PYMS_PORT` | `8000` | 监听端口 |
| `PYMS_DB_PATH` | `data/app.db` | 数据库路径 |
| `PYMS_API_KEY` | （空） | API Key（设置后启用鉴权） |
