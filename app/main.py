from __future__ import annotations

import logging
import traceback
from pathlib import Path

import jinja2
from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from jinja2 import FileSystemBytecodeCache

from app.config import app_settings, is_qc_mode_enabled
from app.db import initialize_database
from app.routers.admin_router import admin_router
from app.routers.auth_router import auth_router
from app.routers.tracking_router import tracking_router
from app.services.backup_service import start_backup_daemon
from app.services.logging_service import initialize_logging, get_logger

_logger = get_logger("main")


def _bridge_uvicorn_logs_to_app_log() -> None:
    app_root = logging.getLogger("product_test")
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "sqlalchemy.engine"):
        ext = logging.getLogger(name)
        ext.handlers.clear()
        ext.propagate = False
        for handler in app_root.handlers:
            ext.addHandler(handler)
        ext.setLevel(logging.INFO)


def create_app() -> FastAPI:
    app = FastAPI(
        title=app_settings.project_name,
        version=app_settings.project_version,
    )

    templates_directory_path = Path(__file__).resolve().parent / "templates"
    bytecode_directory_path = app_settings.base_directory_path.parent / ".jinja2_cache"
    bytecode_directory_path.mkdir(parents=True, exist_ok=True)
    loader = jinja2.FileSystemLoader(str(templates_directory_path))
    bytecode_cache = FileSystemBytecodeCache(str(bytecode_directory_path))
    template_env = jinja2.Environment(
        loader=loader,
        autoescape=jinja2.select_autoescape(),
        bytecode_cache=bytecode_cache,
    )
    template_env.globals["qc_mode_enabled"] = is_qc_mode_enabled()
    app.state.templates = Jinja2Templates(env=template_env)

    static_directory_path = Path(__file__).resolve().parent / "static"
    app.mount("/static", StaticFiles(directory=str(static_directory_path)), name="static")

    app.include_router(auth_router)
    app.include_router(admin_router)
    app.include_router(tracking_router)

    @app.on_event("startup")
    def on_startup_initialize_database() -> None:
        app_settings.data_directory_path.mkdir(parents=True, exist_ok=True)
        initialize_logging(app_settings.data_directory_path, qc_mode=is_qc_mode_enabled())
        _bridge_uvicorn_logs_to_app_log()
        try:
            initialize_database()
        except Exception as exc:
            _logger.error(
                "[main] DB 초기화 실패: %s\n%s",
                exc,
                traceback.format_exc(),
            )
            raise
        start_backup_daemon(app_settings.data_directory_path)
        _logger.info(
            "[main] 서버 시작 완료  host=%s  port=%s",
            app_settings.server_runtime_config.host,
            app_settings.server_runtime_config.port,
        )

    @app.exception_handler(HTTPException)
    async def _http_exception_handler(request: Request, exc: HTTPException):
        _logger.warning(
            "[main] HTTP 예외  method=%s  url=%s  status=%s  detail=%s",
            request.method, request.url, exc.status_code, exc.detail,
        )
        return await http_exception_handler(request, exc)

    @app.exception_handler(RequestValidationError)
    async def _validation_exception_handler(request: Request, exc: RequestValidationError):
        _logger.warning(
            "[main] 유효성 검사 실패  method=%s  url=%s  errors=%s",
            request.method, request.url, exc.errors(),
        )
        return await request_validation_exception_handler(request, exc)

    @app.exception_handler(Exception)
    async def _global_exception_handler(request: Request, exc: Exception) -> HTMLResponse:
        if isinstance(exc, (HTTPException, RequestValidationError)):
            raise exc
        _logger.error(
            "[main] 처리되지 않은 예외  method=%s  url=%s\n%s",
            request.method,
            request.url,
            traceback.format_exc(),
        )
        return HTMLResponse(
            content="<h1>500 Internal Server Error</h1><p>서버 내부 오류가 발생했습니다.</p>",
            status_code=500,
        )

    return app


app = create_app()
