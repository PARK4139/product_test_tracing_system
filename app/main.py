from pathlib import Path
import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import app_settings
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
    app.state.templates = Jinja2Templates(directory=str(templates_directory_path))
    app.state.templates.env.globals["qc_mode_enabled"] = (
        os.getenv("QC_MODE", "True").strip().lower() in {"1", "true", "yes", "on"}
    )

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
