from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any
import uuid

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from app.cleaning import export_results, list_results
from app.command_engine import execute_command
from app.config import get_settings
from app.db import init_db
from app.errors import AppError, ERROR_MESSAGES
from app.service import (
    DEFAULT_DEPTH,
    DEFAULT_LIMIT,
    get_task,
    list_event_logs,
    list_queue_items,
    list_tasks,
    log_command,
    submit_task,
)
from app.worker import get_queue_runner
from app.wordclouds import generate_wordcloud


EVENT_STREAM_POLL_INTERVAL_SECONDS = 0.1
EVENT_STREAM_IDLE_TIMEOUT_SECONDS = 5
STATIC_DIR = Path(__file__).resolve().parent / "static"


class SubmitTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    limit: int = Field(default=DEFAULT_LIMIT, ge=1, le=1000)
    depth: int = Field(default=DEFAULT_DEPTH, ge=1, le=5)
    task_name: str | None = None
    renderer: str = Field(default="http", min_length=1)


class CommandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command: str = Field(min_length=1)
    request_id: str | None = None


class ExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: str = Field(min_length=1)


class WordCloudRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    view: str = Field(default="auto", min_length=1)
    width: int = Field(default=1200, ge=320, le=2000)
    height: int = Field(default=720, ge=320, le=2000)
    top_n: int = Field(default=80, ge=10, le=200)


@asynccontextmanager
async def _lifespan(_: FastAPI) -> Any:
    init_db()
    get_queue_runner()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    api = FastAPI(title="PyMS Control Plane", version="0.1.0", lifespan=_lifespan)
    api.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @api.middleware("http")
    async def enforce_api_key(request: Request, call_next: Any) -> JSONResponse | StreamingResponse:
        if not _requires_api_key(request, settings):
            return await call_next(request)

        if _read_api_key(request) != settings.api_key:
            return JSONResponse(
                status_code=401,
                content=_error_payload(_request_id(request), 1004, ERROR_MESSAGES[1004]),
            )
        return await call_next(request)

    @api.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        status_code = 400 if exc.code < 5000 else 500
        if exc.code == 2001:
            status_code = 404
        return JSONResponse(
            status_code=status_code,
            content=_error_payload(_request_id(None), exc.code, exc.message),
        )

    @api.exception_handler(Exception)
    async def handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=_error_payload(_request_id(None), 5000, ERROR_MESSAGES[5000]),
        )

    @api.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content=_error_payload(_request_id(request), 1001, str(exc.errors())),
        )

    @api.get("/v1/health")
    async def health(request: Request) -> dict[str, Any]:
        return _ok_payload(
            _request_id(request),
            {
                "status": "ok",
                "version": "0.1.0",
                "environment": settings.app_env,
                "auth": {"api_key_required": settings.api_key_enabled},
                "storage": {
                    "db_url": settings.db_url,
                    "redis_url": settings.redis_url,
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    @api.get("/", response_class=FileResponse)
    async def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @api.get("/v1/tasks")
    async def tasks(request: Request, task_id: str | None = None) -> dict[str, Any]:
        data = get_task(task_id) if task_id else list_tasks()
        return _ok_payload(_request_id(request), data)

    @api.get("/v1/tasks/{task_id}")
    async def task_detail(task_id: str, request: Request) -> dict[str, Any]:
        return _ok_payload(_request_id(request), get_task(task_id))

    @api.get("/v1/tasks/{task_id}/queue")
    async def task_queue(
        task_id: str,
        request: Request,
        state: str | None = None,
        page: int = 1,
        page_size: int | None = None,
    ) -> dict[str, Any]:
        return _ok_payload(_request_id(request), list_queue_items(task_id, state, page=page, page_size=page_size))

    @api.get("/v1/tasks/{task_id}/results")
    async def task_results(
        task_id: str,
        request: Request,
        view: str = "clean",
        page: int = 1,
        page_size: int = 20,
        q: str | None = None,
    ) -> dict[str, Any]:
        return _ok_payload(
            _request_id(request),
            list_results(task_id=task_id, view=view, page=page, page_size=page_size, query=q),
        )

    @api.post("/v1/tasks/{task_id}/export")
    async def task_export(task_id: str, payload: ExportRequest) -> StreamingResponse:
        exported = export_results(task_id, payload.format)
        headers = {
            "Content-Disposition": f'attachment; filename="{exported["filename"]}"',
        }
        return StreamingResponse(
            BytesIO(exported["content"]),
            media_type=exported["media_type"],
            headers=headers,
        )

    @api.post("/v1/tasks/{task_id}/wordcloud")
    async def task_wordcloud(task_id: str, payload: WordCloudRequest) -> StreamingResponse:
        generated = generate_wordcloud(
            task_id=task_id,
            view=payload.view,
            width=payload.width,
            height=payload.height,
            top_n=payload.top_n,
        )
        headers = {
            "Content-Disposition": f'inline; filename="{generated["filename"]}"',
            "X-Wordcloud-View": generated["view"],
            "X-Wordcloud-Top-Terms": json.dumps(generated["top_terms"], ensure_ascii=True),
        }
        return StreamingResponse(
            BytesIO(generated["content"]),
            media_type=generated["media_type"],
            headers=headers,
        )

    @api.get("/v1/events/stream")
    async def event_stream(
        task_id: str,
        request: Request,
        after_id: int = 0,
    ) -> StreamingResponse:
        get_task(task_id)

        async def generate() -> Any:
            last_id = after_id
            idle_started_at = asyncio.get_running_loop().time()

            while True:
                if await request.is_disconnected():
                    break

                try:
                    events = list_event_logs(task_id=task_id, after_id=last_id, limit=100)
                except AppError as exc:
                    if exc.code == 2001:
                        return
                    raise
                if events:
                    idle_started_at = asyncio.get_running_loop().time()
                    for event in events:
                        last_id = event["id"]
                        yield _sse_frame("message", event, event_id=event["id"])
                else:
                    try:
                        current_task = get_task(task_id)
                    except AppError as exc:
                        if exc.code == 2001:
                            return
                        raise
                    idle_seconds = asyncio.get_running_loop().time() - idle_started_at
                    if current_task["status"] in {"success", "failed", "stopped"} and idle_seconds >= 0.2:
                        return
                    if idle_seconds >= EVENT_STREAM_IDLE_TIMEOUT_SECONDS:
                        yield _sse_frame("keepalive", {"task_id": task_id, "message": "idle timeout"})
                        return
                    yield ": keepalive\n\n"
                    await asyncio.sleep(EVENT_STREAM_POLL_INTERVAL_SECONDS)

        return StreamingResponse(generate(), media_type="text/event-stream")

    @api.post("/v1/crawl/submit", status_code=201)
    async def crawl_submit(payload: SubmitTaskRequest, request: Request) -> dict[str, Any]:
        data = submit_task(payload.model_dump())
        return _ok_payload(_request_id(request), data, message="task created")

    @api.post("/v1/command")
    async def command(payload: CommandRequest, request: Request) -> dict[str, Any]:
        request_id = payload.request_id or _request_id(request)
        try:
            data = execute_command(payload.command)
        except AppError as exc:
            log_command(request_id, payload.command, exc.code, exc.message)
            status_code = 400 if exc.code < 5000 else 500
            if exc.code == 2001:
                status_code = 404
            return JSONResponse(
                status_code=status_code,
                content=_error_payload(request_id, exc.code, exc.message),
            )

        log_command(request_id, payload.command, 0, "ok")
        return _ok_payload(request_id, data)

    return api


app = create_app()


def run(host: str | None = None, port: int | None = None) -> None:
    settings = get_settings()
    uvicorn.run(app, host=host or settings.host, port=port or settings.port)


def _requires_api_key(request: Request, settings: Any) -> bool:
    if not settings.api_key_enabled:
        return False
    path = request.url.path
    if path == "/" or path == "/v1/health" or path.startswith("/static/"):
        return False
    return path.startswith("/v1/")


def _read_api_key(request: Request) -> str | None:
    authorization = request.headers.get("Authorization", "")
    if authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        if token:
            return token
    x_api_key = request.headers.get("X-API-Key")
    if x_api_key and x_api_key.strip():
        return x_api_key.strip()
    query_api_key = request.query_params.get("api_key")
    if query_api_key and query_api_key.strip():
        return query_api_key.strip()
    return None


def _request_id(request: Request | None) -> str:
    if request is None:
        return f"req_{uuid.uuid4().hex[:12]}"
    return request.headers.get("X-Request-Id") or f"req_{uuid.uuid4().hex[:12]}"


def _ok_payload(request_id: str, data: Any, message: str = "ok") -> dict[str, Any]:
    return {
        "code": 0,
        "message": message,
        "request_id": request_id,
        "data": data,
    }


def _error_payload(request_id: str, code: int, message: str) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "request_id": request_id,
        "data": None,
    }


def _sse_frame(event: str, data: dict[str, Any], event_id: int | None = None) -> str:
    lines: list[str] = []
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event}")
    lines.append(f"data: {json.dumps(data, ensure_ascii=True)}")
    return "\n".join(lines) + "\n\n"
