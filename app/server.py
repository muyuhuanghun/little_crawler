from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import uuid

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.command_engine import execute_command
from app.db import init_db
from app.errors import AppError, ERROR_MESSAGES
from app.service import DEFAULT_DEPTH, DEFAULT_LIMIT, get_task, list_tasks, log_command, submit_task


HOST = "127.0.0.1"
PORT = 8000


class SubmitTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    limit: int = Field(default=DEFAULT_LIMIT, ge=1, le=1000)
    depth: int = Field(default=DEFAULT_DEPTH, ge=1, le=5)
    task_name: str | None = None


class CommandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command: str = Field(min_length=1)
    request_id: str | None = None


def create_app() -> FastAPI:
    api = FastAPI(title="PyMS Control Plane", version="0.1.0")

    @api.on_event("startup")
    def on_startup() -> None:
        init_db()

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
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    @api.get("/v1/tasks")
    async def tasks(request: Request, task_id: str | None = None) -> dict[str, Any]:
        data = get_task(task_id) if task_id else list_tasks()
        return _ok_payload(_request_id(request), data)

    @api.get("/v1/tasks/{task_id}")
    async def task_detail(task_id: str, request: Request) -> dict[str, Any]:
        return _ok_payload(_request_id(request), get_task(task_id))

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


def run(host: str = HOST, port: int = PORT) -> None:
    uvicorn.run(app, host=host, port=port)


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
