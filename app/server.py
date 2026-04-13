from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any
import uuid

import redis
import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from app.audit import list_audit_logs, write_audit_log
from app.auth import get_session_user, list_users, login_user, logout_session, register_user, set_user_role
from app.cleaning import export_results, list_results
from app.command_engine import execute_command
from app.config import get_settings
from app.db import init_db, get_connection
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
from app.worker import start_queue_runtime
from app.wordclouds import generate_wordcloud


EVENT_STREAM_POLL_INTERVAL_SECONDS = 0.1
EVENT_STREAM_IDLE_TIMEOUT_SECONDS = 5
STATIC_DIR = Path(__file__).resolve().parent / "static"
SESSION_COOKIE_NAME = "pyms_session"
REQUEST_COUNTERS: dict[tuple[str, str, str], int] = {}


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


class AuthRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)


class RoleUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str = Field(min_length=1, max_length=32)


@asynccontextmanager
async def _lifespan(_: FastAPI) -> Any:
    init_db()
    start_queue_runtime()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    api = FastAPI(title="PyMS Control Plane", version="0.1.0", lifespan=_lifespan)
    api.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @api.middleware("http")
    async def attach_request_id(request: Request, call_next: Any) -> JSONResponse | StreamingResponse:
        request.state.request_id = request.headers.get("X-Request-Id") or f"req_{uuid.uuid4().hex[:12]}"
        return await call_next(request)

    @api.middleware("http")
    async def collect_metrics(request: Request, call_next: Any) -> JSONResponse | StreamingResponse:
        response = await call_next(request)
        key = (request.method, request.url.path, str(response.status_code))
        REQUEST_COUNTERS[key] = REQUEST_COUNTERS.get(key, 0) + 1
        if settings.audit_log_enabled and _requires_audit_log(request):
            try:
                write_audit_log(
                    user=getattr(request.state, "user", None),
                    action=f"{request.method} {request.url.path}",
                    resource=request.url.path,
                    status_code=int(response.status_code),
                    request_id=_request_id(request),
                    source_ip=(request.client.host if request.client else None),
                    user_agent=request.headers.get("User-Agent"),
                    payload={"query": dict(request.query_params)},
                )
            except Exception:
                # Audit log must not break main request path.
                pass
        return response

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

    @api.middleware("http")
    async def enforce_session_auth(request: Request, call_next: Any) -> JSONResponse | StreamingResponse:
        if not _requires_session_auth(request, settings):
            return await call_next(request)

        token = _read_session_token(request)
        user = get_session_user(token or "")
        if user is None:
            return JSONResponse(
                status_code=401,
                content=_error_payload(_request_id(request), 1004, "login required"),
            )
        request.state.user = user
        return await call_next(request)

    @api.middleware("http")
    async def enforce_rbac(request: Request, call_next: Any) -> JSONResponse | StreamingResponse:
        if not settings.auth_enabled or not request.url.path.startswith("/v1/"):
            return await call_next(request)
        if not _requires_session_auth(request, settings):
            return await call_next(request)

        user = getattr(request.state, "user", None)
        if user is None:
            token = _read_session_token(request)
            user = get_session_user(token or "")
            if user is not None:
                request.state.user = user
        if user is None:
            return JSONResponse(
                status_code=401,
                content=_error_payload(_request_id(request), 1004, "login required"),
            )
        role = (user or {}).get("role", "")
        required = _required_role_for_request(request)
        if required == "admin" and role != "admin":
            return JSONResponse(
                status_code=403,
                content=_error_payload(_request_id(request), 1004, "admin role required"),
            )
        if required == "operator" and role not in {"operator", "admin"}:
            return JSONResponse(
                status_code=403,
                content=_error_payload(_request_id(request), 1004, "operator role required"),
            )
        return await call_next(request)

    @api.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        status_code = 400 if exc.code < 5000 else 500
        if exc.code == 1004:
            status_code = 401
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
        checks = _runtime_probe(settings)
        return _ok_payload(
            _request_id(request),
            {
                "status": "ok" if checks["ok"] else "degraded",
                "version": "0.1.0",
                "environment": settings.app_env,
                "auth": {
                    "api_key_required": settings.api_key_enabled,
                    "session_enabled": settings.auth_enabled,
                },
                "storage": {
                    "db_url": settings.db_url,
                    "redis_url": settings.redis_url,
                },
                "runtime": {
                    "queue_backend": settings.queue_backend,
                },
                "checks": checks["checks"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    @api.get("/v1/runtime/probe")
    async def runtime_probe(request: Request) -> dict[str, Any]:
        checks = _runtime_probe(settings)
        return _ok_payload(_request_id(request), checks)

    @api.get("/v1/metrics")
    async def metrics() -> PlainTextResponse:
        return PlainTextResponse(_render_prometheus_metrics(), media_type="text/plain; version=0.0.4")

    @api.get("/", response_class=FileResponse)
    async def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @api.post("/v1/auth/register")
    async def auth_register(payload: AuthRequest, request: Request) -> dict[str, Any]:
        data = register_user(payload.username, payload.password)
        return _ok_payload(_request_id(request), data, message="user registered")

    @api.post("/v1/auth/login")
    async def auth_login(payload: AuthRequest, request: Request) -> JSONResponse:
        data = login_user(payload.username, payload.password)
        response = JSONResponse(
            status_code=200,
            content=_ok_payload(_request_id(request), {"user": data["user"], "expires_at": data["expires_at"]}),
        )
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=data["token"],
            httponly=True,
            secure=settings.app_env not in {"development", "test"},
            samesite="lax",
            max_age=settings.session_ttl_hours * 3600,
            path="/",
        )
        return response

    @api.post("/v1/auth/logout")
    async def auth_logout(request: Request) -> JSONResponse:
        token = _read_session_token(request)
        if token:
            logout_session(token)
        response = JSONResponse(
            status_code=200,
            content=_ok_payload(_request_id(request), {"logged_out": True}),
        )
        response.delete_cookie(SESSION_COOKIE_NAME, path="/")
        return response

    @api.get("/v1/auth/me")
    async def auth_me(request: Request) -> dict[str, Any]:
        token = _read_session_token(request)
        user = get_session_user(token or "")
        if user is None:
            raise AppError(1004, "login required")
        return _ok_payload(_request_id(request), {"user": user})

    @api.get("/v1/auth/users")
    async def auth_users(request: Request) -> dict[str, Any]:
        return _ok_payload(_request_id(request), {"items": list_users()})

    @api.post("/v1/auth/users/{user_id}/role")
    async def auth_set_role(user_id: int, payload: RoleUpdateRequest, request: Request) -> dict[str, Any]:
        updated = set_user_role(user_id=user_id, role=payload.role)
        return _ok_payload(_request_id(request), updated, message="role updated")

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
            if exc.code == 1004:
                status_code = 401
            if exc.code == 2001:
                status_code = 404
            return JSONResponse(
                status_code=status_code,
                content=_error_payload(request_id, exc.code, exc.message),
            )

        log_command(request_id, payload.command, 0, "ok")
        return _ok_payload(request_id, data)

    @api.get("/v1/audit/logs")
    async def audit_logs(request: Request, page: int = 1, page_size: int = 50) -> dict[str, Any]:
        return _ok_payload(_request_id(request), list_audit_logs(page=page, page_size=page_size))

    return api


app = create_app()


def run(host: str | None = None, port: int | None = None) -> None:
    settings = get_settings()
    uvicorn.run(app, host=host or settings.host, port=port or settings.port)


def _requires_api_key(request: Request, settings: Any) -> bool:
    if not settings.api_key_enabled:
        return False
    path = request.url.path
    if (
        path == "/"
        or path in {"/v1/health", "/v1/metrics", "/v1/runtime/probe"}
        or path.startswith("/static/")
        or path.startswith("/v1/auth/")
    ):
        return False
    return path.startswith("/v1/")


def _requires_session_auth(request: Request, settings: Any) -> bool:
    if not settings.auth_enabled:
        return False
    path = request.url.path
    if (
        path == "/"
        or path in {"/v1/health", "/v1/metrics", "/v1/runtime/probe"}
        or path.startswith("/static/")
        or path.startswith("/v1/auth/register")
        or path.startswith("/v1/auth/login")
    ):
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


def _read_session_token(request: Request) -> str | None:
    authorization = request.headers.get("Authorization", "")
    if authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        if token:
            return token
    x_session = request.headers.get("X-Session-Token")
    if x_session and x_session.strip():
        return x_session.strip()
    cookie_token = request.cookies.get(SESSION_COOKIE_NAME)
    if cookie_token and cookie_token.strip():
        return cookie_token.strip()
    return None


def _request_id(request: Request | None) -> str:
    if request is None:
        return f"req_{uuid.uuid4().hex[:12]}"
    state_request_id = getattr(request.state, "request_id", None)
    if state_request_id:
        return state_request_id
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


def _runtime_probe(settings: Any) -> dict[str, Any]:
    checks: dict[str, dict[str, Any]] = {}

    try:
        with get_connection() as connection:
            connection.execute("SELECT 1")
        checks["database"] = {"ok": True}
    except Exception as exc:
        checks["database"] = {"ok": False, "error": str(exc)}

    try:
        redis.Redis.from_url(settings.redis_url, socket_timeout=1.0).ping()
        checks["redis"] = {"ok": True}
    except Exception as exc:
        checks["redis"] = {"ok": False, "error": str(exc)}

    if settings.queue_backend == "celery":
        checks["queue_backend"] = {"ok": checks["redis"]["ok"], "backend": "celery"}
    elif settings.queue_backend == "inprocess":
        checks["queue_backend"] = {"ok": True, "backend": "inprocess"}
    else:
        checks["queue_backend"] = {"ok": True, "backend": settings.queue_backend}

    overall_ok = all(item.get("ok", False) for item in checks.values())
    return {"ok": overall_ok, "checks": checks}


def _render_prometheus_metrics() -> str:
    lines = [
        "# HELP pyms_http_requests_total Total HTTP requests by method/path/status.",
        "# TYPE pyms_http_requests_total counter",
    ]
    for (method, path, status), count in sorted(REQUEST_COUNTERS.items()):
        lines.append(
            f'pyms_http_requests_total{{method="{method}",path="{path}",status="{status}"}} {count}'
        )
    return "\n".join(lines) + "\n"


def _requires_audit_log(request: Request) -> bool:
    path = request.url.path
    if path == "/" or path.startswith("/static/"):
        return False
    if path in {"/v1/health", "/v1/metrics", "/v1/runtime/probe"}:
        return False
    return path.startswith("/v1/")


def _required_role_for_request(request: Request) -> str:
    path = request.url.path
    method = request.method.upper()

    if path.startswith("/v1/auth/users") or path.startswith("/v1/audit/logs"):
        return "admin"

    if method in {"GET", "HEAD", "OPTIONS"}:
        return "viewer"

    if path.startswith("/v1/auth/logout"):
        return "viewer"

    return "operator"
