from pathlib import Path

import jinja2
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from jinja2 import FileSystemBytecodeCache

from app.config import app_settings, is_qc_mode_enabled
from app.db import initialize_database
from app.routers.admin_router import admin_router
from app.routers.auth_router import auth_router
from app.routers.export_router import export_router
from app.routers.product_test_tester_router import product_test_tester_router
from app.routers.submission_router import submission_router
from app.routers.tester_router import tester_router


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
    app.include_router(submission_router)
    app.include_router(tester_router)
    app.include_router(product_test_tester_router)
    app.include_router(admin_router)
    app.include_router(export_router)

    @app.on_event("startup")
    def on_startup_initialize_database() -> None:
        app_settings.data_directory_path.mkdir(parents=True, exist_ok=True)
        initialize_database()

    return app


app = create_app()
