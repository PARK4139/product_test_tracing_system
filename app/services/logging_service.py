"""
Logging service for product_test_tracing_system.

pk_system 로깅 패턴 참고:
- RotatingFileHandler: 50 MB per file, 10 backups  →  data/logs/app.log
- 파일 출력: plain text (ANSI 제거)
- 콘솔 출력: QC 모드일 때 컬러, 아닐 때 plain
- log_info / log_warning / log_error / log_debug  →  pk_system log0/log1/log2 대응
  포맷: {timestamp} [{title}] {text}
"""

from __future__ import annotations

import logging
import logging.handlers
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── constants ──────────────────────────────────────────────────────────────────
_LOG_MAX_BYTES = 50 * 1024 * 1024   # 50 MB
_LOG_BACKUP_COUNT = 10

_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")

_initialized = False
_root_logger: logging.Logger | None = None


# ── ANSI colors ────────────────────────────────────────────────────────────────

class _C:
    RESET   = "\x1b[0m"
    BOLD    = "\x1b[1m"
    GREY    = "\x1b[38;5;243m"
    CYAN    = "\x1b[36m"
    GREEN   = "\x1b[32m"
    YELLOW  = "\x1b[33m"
    RED     = "\x1b[31m"
    MAGENTA = "\x1b[35m"
    WHITE   = "\x1b[37m"


# ── formatters ─────────────────────────────────────────────────────────────────

class _PlainFormatter(logging.Formatter):
    """ANSI 없는 plain text — 파일 출력용."""

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        msg = record.getMessage()
        msg = _ANSI_ESCAPE_RE.sub("", msg)
        if record.exc_info:
            exc = self.formatException(record.exc_info)
            msg = f"{msg}\n{_ANSI_ESCAPE_RE.sub('', exc)}"
        return f"{ts} [{record.levelname}] {msg}"


class _ColoredFormatter(logging.Formatter):
    """컬러 콘솔 출력 — QC 모드 전용."""

    _COLORS: dict[int, str] = {
        logging.DEBUG:    _C.GREY,
        logging.INFO:     _C.CYAN,
        logging.WARNING:  _C.YELLOW,
        logging.ERROR:    _C.RED,
        logging.CRITICAL: _C.MAGENTA,
    }

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        color = self._COLORS.get(record.levelno, _C.WHITE)
        msg = record.getMessage()
        if record.exc_info:
            msg = f"{msg}\n{self.formatException(record.exc_info)}"
        return (
            f"{_C.GREY}{ts}{_C.RESET} "
            f"{color}{_C.BOLD}[{record.levelname}]{_C.RESET} "
            f"{color}{msg}{_C.RESET}"
        )


# ── Windows-safe RotatingFileHandler ──────────────────────────────────────────

class _SafeRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """PermissionError(Windows 파일 잠금) 시 rotation 건너뜀."""

    def doRollover(self) -> None:
        try:
            super().doRollover()
        except PermissionError:
            pass  # 다른 프로세스가 파일 열고 있으면 그냥 이번 rotation 스킵


# ── initialization ─────────────────────────────────────────────────────────────

def initialize_logging(data_directory_path: Path, qc_mode: bool) -> None:
    """앱 시작 시 1회 호출. data/logs/app.log 에 rotating 파일 로그 설정."""
    global _initialized, _root_logger
    if _initialized:
        return

    logs_dir = data_directory_path / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file_path = logs_dir / "app.log"

    root = logging.getLogger("product_test")
    root.setLevel(logging.DEBUG)
    root.handlers.clear()

    # 파일 핸들러 (항상 켜짐)
    file_handler = _SafeRotatingFileHandler(
        filename=str(log_file_path),
        maxBytes=_LOG_MAX_BYTES,
        backupCount=_LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(_PlainFormatter())
    root.addHandler(file_handler)

    # 콘솔 핸들러
    console_handler = logging.StreamHandler(sys.stdout)
    if qc_mode:
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(_ColoredFormatter())
    else:
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(_PlainFormatter())
    root.addHandler(console_handler)

    root.propagate = False
    _root_logger = root
    _initialized = True

    root.info(
        "[logging_service] initialized  path=%s  qc_mode=%s",
        log_file_path,
        qc_mode,
    )


def get_logger(module_name: str) -> logging.Logger:
    """product_test.<module_name> 네임스페이스 로거 반환."""
    return logging.getLogger(f"product_test.{module_name}")


# ── convenience helpers (pk_system log0/log1/log2 대응) ────────────────────────
# 포맷: {timestamp} [{title}] {text}

def _root() -> logging.Logger:
    if _root_logger is not None:
        return _root_logger
    # initialize_logging 호출 전 fallback
    fallback = logging.getLogger("product_test")
    if not fallback.handlers:
        fallback.setLevel(logging.DEBUG)
        h = logging.StreamHandler(sys.stderr)
        h.setFormatter(_PlainFormatter())
        fallback.addHandler(h)
    return fallback


def log_info(title: str, text: str = "") -> None:
    _root().info("[%s] %s", title, text)


def log_warning(title: str, text: str = "") -> None:
    _root().warning("[%s] %s", title, text)


def log_error(title: str, text: str = "", *, exc_info: bool = False) -> None:
    _root().error("[%s] %s", title, text, exc_info=exc_info)


def log_debug(title: str, text: str = "") -> None:
    _root().debug("[%s] %s", title, text)
