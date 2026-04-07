-- 网页爬虫控制台
-- 核心数据表 DDL v1.0
-- 目标数据库：PostgreSQL 14+

BEGIN;

-- 1) 任务表：tasks
CREATE TABLE IF NOT EXISTS tasks (
    task_id              VARCHAR(64) PRIMARY KEY,
    task_name            VARCHAR(128),
    root_url             TEXT NOT NULL,
    status               VARCHAR(16) NOT NULL CHECK (status IN ('pending', 'running', 'paused', 'stopped', 'success', 'failed')),
    limit_count          INTEGER NOT NULL DEFAULT 50 CHECK (limit_count > 0),
    depth                INTEGER NOT NULL DEFAULT 1 CHECK (depth > 0),

    total_count          INTEGER NOT NULL DEFAULT 0 CHECK (total_count >= 0),
    done_count           INTEGER NOT NULL DEFAULT 0 CHECK (done_count >= 0),
    failed_count         INTEGER NOT NULL DEFAULT 0 CHECK (failed_count >= 0),
    clean_done_count     INTEGER NOT NULL DEFAULT 0 CHECK (clean_done_count >= 0),

    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at           TIMESTAMPTZ,
    ended_at             TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_tasks_status_created_at ON tasks (status, created_at DESC);

-- 2) 队列表：queue_items
CREATE TABLE IF NOT EXISTS queue_items (
    id                   BIGSERIAL PRIMARY KEY,
    task_id              VARCHAR(64) NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
    url                  TEXT NOT NULL,
    state                VARCHAR(16) NOT NULL CHECK (state IN ('pending', 'running', 'done', 'failed', 'canceled')),
    retry_count          INTEGER NOT NULL DEFAULT 0 CHECK (retry_count >= 0),
    priority             INTEGER NOT NULL DEFAULT 100,
    next_run_at          TIMESTAMPTZ,
    last_error           TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_queue_task_url UNIQUE (task_id, url)
);

CREATE INDEX IF NOT EXISTS idx_queue_task_state_priority ON queue_items (task_id, state, priority, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_queue_next_run_at ON queue_items (next_run_at);

-- 3) 原始数据表：raw_items
CREATE TABLE IF NOT EXISTS raw_items (
    id                   BIGSERIAL PRIMARY KEY,
    task_id              VARCHAR(64) NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
    news_id              TEXT,
    news_date            VARCHAR(32),
    news_title           TEXT,
    news_content         TEXT,
    source_url           TEXT NOT NULL,
    fetched_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw_payload_json     JSONB
);

CREATE INDEX IF NOT EXISTS idx_raw_task_fetched_at ON raw_items (task_id, fetched_at DESC);
CREATE INDEX IF NOT EXISTS idx_raw_task_news_id ON raw_items (task_id, news_id);

-- 4) 清洗结果表：clean_items
CREATE TABLE IF NOT EXISTS clean_items (
    id                   BIGSERIAL PRIMARY KEY,
    raw_id               BIGINT NOT NULL REFERENCES raw_items(id) ON DELETE CASCADE,
    task_id              VARCHAR(64) NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
    clean_news_date      VARCHAR(32),
    clean_news_title     TEXT,
    clean_news_content   TEXT,
    dedup_key            VARCHAR(128) NOT NULL,
    clean_status         VARCHAR(16) NOT NULL CHECK (clean_status IN ('clean_done', 'clean_failed')),
    cleaned_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_clean_task_dedup UNIQUE (task_id, dedup_key)
);

CREATE INDEX IF NOT EXISTS idx_clean_task_status_cleaned_at ON clean_items (task_id, clean_status, cleaned_at DESC);
CREATE INDEX IF NOT EXISTS idx_clean_raw_id ON clean_items (raw_id);

-- 5) 命令日志表：command_logs
CREATE TABLE IF NOT EXISTS command_logs (
    id                   BIGSERIAL PRIMARY KEY,
    request_id           VARCHAR(64) NOT NULL,
    command              TEXT NOT NULL,
    result_code          INTEGER NOT NULL,
    result_message       TEXT NOT NULL,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_command_logs_request_id ON command_logs (request_id);
CREATE INDEX IF NOT EXISTS idx_command_logs_created_at ON command_logs (created_at DESC);

-- 6) 事件日志表：event_logs
CREATE TABLE IF NOT EXISTS event_logs (
    id                   BIGSERIAL PRIMARY KEY,
    task_id              VARCHAR(64) NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
    event_type           VARCHAR(64) NOT NULL,
    payload_json         JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_event_logs_task_created_at ON event_logs (task_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_event_logs_event_type ON event_logs (event_type);

-- 7) queue_items 的 updated_at 自动更新时间触发器
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_queue_items_updated_at ON queue_items;
CREATE TRIGGER trg_queue_items_updated_at
BEFORE UPDATE ON queue_items
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

COMMIT;

-- 可选初始化示例：
-- INSERT INTO tasks(task_id, task_name, root_url, status) VALUES ('task_demo_001', '演示任务', 'https://news.uestc.edu.cn', 'pending');
