from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


def _parse_bool(value: object, default_value: bool) -> bool:
    if value is None:
        return default_value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default_value


def parse_config_bool(value: object, default_value: bool) -> bool:
    """Parse boolean from JSON/env style values (server config, tests, optional env overrides)."""
    return _parse_bool(value, default_value)


@dataclass(frozen=True)
class ServerRuntimeConfig:
    host: str
    port: int
    qc_mode: bool
    kiosk_mode: bool


@dataclass(frozen=True)
class AppSettings:
    project_name: str
    project_version: str
    base_directory_path: Path
    data_directory_path: Path
    sqlite_database_file_path: Path
    sqlite_database_url: str
    server_config_file_path: Path
    server_runtime_config: ServerRuntimeConfig


def _default_server_config_payload() -> dict[str, object]:
    return {
        "host": "127.0.0.1",
        "port": 8008,
        "qc_mode": True,
        "kiosk_mode": True,
    }


def _load_server_runtime_config(server_config_file_path: Path) -> ServerRuntimeConfig:
    default_payload = _default_server_config_payload()
    if not server_config_file_path.exists():
        server_config_file_path.write_text(
            json.dumps(default_payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        payload = default_payload
    else:
        payload = default_payload
        try:
            raw_payload = json.loads(server_config_file_path.read_text(encoding="utf-8"))
            if isinstance(raw_payload, dict):
                payload = {**default_payload, **raw_payload}
        except Exception:
            payload = default_payload

    host = str(payload.get("host") or default_payload["host"]).strip() or str(default_payload["host"])
    port_value = payload.get("port", default_payload["port"])
    try:
        port = int(port_value)
    except (TypeError, ValueError):
        port = int(default_payload["port"])
    if port <= 0:
        port = int(default_payload["port"])

    return ServerRuntimeConfig(
        host=host,
        port=port,
        qc_mode=parse_config_bool(payload.get("qc_mode"), bool(default_payload["qc_mode"])),
        kiosk_mode=parse_config_bool(payload.get("kiosk_mode"), bool(default_payload["kiosk_mode"])),
    )


def build_app_settings() -> AppSettings:
    base_directory_path = Path(__file__).resolve().parent
    project_root_path = base_directory_path.parent
    data_directory_path = project_root_path / "data"
    env_sqlite_url = (os.environ.get("PRODUCT_TEST_SQLITE_URL") or "").strip()
    if env_sqlite_url:
        sqlite_database_url = env_sqlite_url
        candidate_path: Path | None = None
        if env_sqlite_url.startswith("sqlite:///"):
            remainder = env_sqlite_url[len("sqlite:///") :]
            if remainder and not remainder.startswith(":"):
                candidate_path = Path(remainder)
        sqlite_database_file_path = candidate_path or (data_directory_path / "product_test_tracking_system.db")
    else:
        sqlite_database_file_path = data_directory_path / "product_test_tracking_system.db"
        sqlite_database_url = f"sqlite:///{sqlite_database_file_path.as_posix()}"
    server_config_file_path = project_root_path / "server_config.json"
    server_runtime_config = _load_server_runtime_config(server_config_file_path=server_config_file_path)
    return AppSettings(
        project_name="product_test_tracking_system",
        project_version="0.1.0",
        base_directory_path=base_directory_path,
        data_directory_path=data_directory_path,
        sqlite_database_file_path=sqlite_database_file_path,
        sqlite_database_url=sqlite_database_url,
        server_config_file_path=server_config_file_path,
        server_runtime_config=server_runtime_config,
    )


app_settings = build_app_settings()


def is_qc_mode_enabled() -> bool:
    raw = os.environ.get("PRODUCT_TEST_QC_MODE")
    if raw is not None and str(raw).strip() != "":
        return parse_config_bool(raw, app_settings.server_runtime_config.qc_mode)
    return app_settings.server_runtime_config.qc_mode


def is_kiosk_mode_enabled() -> bool:
    raw = os.environ.get("PRODUCT_TEST_KIOSK_MODE")
    if raw is not None and str(raw).strip() != "":
        return parse_config_bool(raw, app_settings.server_runtime_config.kiosk_mode)
    return app_settings.server_runtime_config.kiosk_mode


def get_server_host() -> str:
    return app_settings.server_runtime_config.host


def get_server_port() -> int:
    return app_settings.server_runtime_config.port
