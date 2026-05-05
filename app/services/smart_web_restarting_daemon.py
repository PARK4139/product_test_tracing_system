import ctypes
import ctypes.wintypes
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer


def _log(message: str) -> None:
    print(f"[smart_web_restarting_daemon] {message}", flush=True)


def _fallback_focus_browser_window_by_title_segments() -> bool:
    if os.name != "nt":
        return False
    title_segments = (
        "Product Test Data Tracing System",
        "127.0.0.1:8000",
        "Product Test",
        "Chrome",
    )

    try:
        user32 = ctypes.windll.user32
        enum_windows_proc_type = ctypes.WINFUNCTYPE(
            ctypes.c_bool,
            ctypes.wintypes.HWND,
            ctypes.wintypes.LPARAM,
        )
        user32.EnumWindows.argtypes = [enum_windows_proc_type, ctypes.wintypes.LPARAM]
        user32.EnumWindows.restype = ctypes.c_bool
        user32.IsWindowVisible.argtypes = [ctypes.wintypes.HWND]
        user32.IsWindowVisible.restype = ctypes.c_bool
        user32.GetWindowTextLengthW.argtypes = [ctypes.wintypes.HWND]
        user32.GetWindowTextLengthW.restype = ctypes.c_int
        user32.GetWindowTextW.argtypes = [
            ctypes.wintypes.HWND,
            ctypes.wintypes.LPWSTR,
            ctypes.c_int,
        ]
        user32.GetWindowTextW.restype = ctypes.c_int
        user32.ShowWindow.argtypes = [ctypes.wintypes.HWND, ctypes.c_int]
        user32.ShowWindow.restype = ctypes.c_bool
        user32.SetForegroundWindow.argtypes = [ctypes.wintypes.HWND]
        user32.SetForegroundWindow.restype = ctypes.c_bool
        user32.BringWindowToTop.argtypes = [ctypes.wintypes.HWND]
        user32.BringWindowToTop.restype = ctypes.c_bool
        user32.AllowSetForegroundWindow.argtypes = [ctypes.wintypes.DWORD]
        user32.AllowSetForegroundWindow.restype = ctypes.c_bool

        found_hwnd = ctypes.wintypes.HWND(0)

        def _enum_windows_proc(hwnd, _l_param):
            if not user32.IsWindowVisible(hwnd):
                return True
            title_length = user32.GetWindowTextLengthW(hwnd)
            if title_length <= 0:
                return True
            title_buffer = ctypes.create_unicode_buffer(title_length + 1)
            user32.GetWindowTextW(hwnd, title_buffer, title_length + 1)
            title_text = title_buffer.value or ""
            if any(title_segment in title_text for title_segment in title_segments):
                found_hwnd.value = hwnd
                return False
            return True

        callback = enum_windows_proc_type(_enum_windows_proc)
        user32.EnumWindows(callback, 0)
        if not found_hwnd.value:
            return False
        user32.AllowSetForegroundWindow(0xFFFFFFFF)  # ASFW_ANY
        user32.ShowWindow(found_hwnd, 9)  # SW_RESTORE
        user32.BringWindowToTop(found_hwnd)
        user32.SetForegroundWindow(found_hwnd)
        return True
    except Exception:
        return False


def _fallback_send_ctrl_alt_r() -> bool:
    if os.name != "nt":
        return False
    try:
        user32 = ctypes.windll.user32
        key_up = 0x0002
        vk_control = 0x11
        vk_alt = 0x12
        vk_r = 0x52
        user32.keybd_event(vk_control, 0, 0, 0)
        user32.keybd_event(vk_alt, 0, 0, 0)
        user32.keybd_event(vk_r, 0, 0, 0)
        user32.keybd_event(vk_r, 0, key_up, 0)
        user32.keybd_event(vk_alt, 0, key_up, 0)
        user32.keybd_event(vk_control, 0, key_up, 0)
        return True
    except Exception:
        return False


def _fallback_send_ctrl_shift_r() -> bool:
    if os.name != "nt":
        return False
    try:
        user32 = ctypes.windll.user32
        key_up = 0x0002
        vk_control = 0x11
        vk_shift = 0x10
        vk_r = 0x52
        user32.keybd_event(vk_control, 0, 0, 0)
        user32.keybd_event(vk_shift, 0, 0, 0)
        user32.keybd_event(vk_r, 0, 0, 0)
        user32.keybd_event(vk_r, 0, key_up, 0)
        user32.keybd_event(vk_shift, 0, key_up, 0)
        user32.keybd_event(vk_control, 0, key_up, 0)
        return True
    except Exception:
        return False


class RestartOnChangeHandler(FileSystemEventHandler):
    def __init__(self, restart_callback: Callable[[Path], None]):
        self.restart_callback = restart_callback
        self._debounce_lock = threading.Lock()
        self._debounce_timer: threading.Timer | None = None
        self._ignored_path_fragments = (
            "\\.git\\",
            "\\.venv\\",
            "\\.uv-cache\\",
            "\\.chrome_qc_profile\\",
            "\\__pycache__\\",
        )

    def _is_ignored_path(self, path_obj: Path) -> bool:
        normalized = str(path_obj).replace("/", "\\").lower()
        return any(fragment in normalized for fragment in self._ignored_path_fragments)

    def on_any_event(self, event) -> None:
        if event.is_directory:
            return
        watched_suffixes = {".py", ".html", ".css", ".js"}
        src_path = Path(getattr(event, "src_path", "") or "")
        dest_path_raw = getattr(event, "dest_path", None)
        dest_path = Path(dest_path_raw) if dest_path_raw else None
        if self._is_ignored_path(src_path):
            return
        if dest_path is not None and self._is_ignored_path(dest_path):
            return

        changed_path = None
        if src_path.suffix.lower() in watched_suffixes:
            changed_path = src_path
        elif dest_path is not None and dest_path.suffix.lower() in watched_suffixes:
            changed_path = dest_path
        if changed_path is None:
            return
        _log(f"file change detected: {changed_path}")

        with self._debounce_lock:
            if self._debounce_timer is not None:
                self._debounce_timer.cancel()
            self._debounce_timer = threading.Timer(
                0.35,
                lambda changed_path=changed_path: self.restart_callback(changed_path),
            )
            self._debounce_timer.daemon = True
            self._debounce_timer.start()


def _trigger_browser_hot_reload_shortcut() -> None:
    used_pk_system_keypress = False
    focused = False
    try:
        from pk_tools.pk_functions.ensure_pressed import ensure_pressed

        used_pk_system_keypress = True
    except Exception:
        used_pk_system_keypress = False

    for _ in range(3):
        focused = _fallback_focus_browser_window_by_title_segments()
        if not focused:
            time.sleep(0.08)

        if used_pk_system_keypress:
            try:
                ensure_pressed("ctrl", "alt", "r")
                _log("hot reload sent via pk_system: Ctrl+Alt+R")
                return
            except Exception:
                pass

        if _fallback_send_ctrl_alt_r():
            _log("hot reload sent via fallback: Ctrl+Alt+R")
            return
        time.sleep(0.06)

    _log("failed to send hot reload shortcut")


def _trigger_browser_hard_reload_shortcut() -> None:
    used_pk_system_keypress = False
    focused = False
    try:
        from pk_tools.pk_functions.ensure_pressed import ensure_pressed

        used_pk_system_keypress = True
    except Exception:
        used_pk_system_keypress = False

    for _ in range(3):
        focused = _fallback_focus_browser_window_by_title_segments()
        if not focused:
            time.sleep(0.08)

        if used_pk_system_keypress:
            try:
                ensure_pressed("ctrl", "shift", "r")
                _log("hard reload sent via pk_system: Ctrl+Shift+R")
                return
            except Exception:
                pass

        if _fallback_send_ctrl_shift_r():
            _log("hard reload sent via fallback: Ctrl+Shift+R")
            return
        time.sleep(0.06)

    _log("failed to send hard reload shortcut")


def run_smart_web_restarting_daemon(
    project_root_path: Path,
    spawn_web_process: Callable[[], subprocess.Popen],
) -> None:
    watched_paths = [project_root_path]
    web_process = spawn_web_process()

    def restart_web_process(changed_path: Path) -> None:
        nonlocal web_process
        suffix = changed_path.suffix.lower()
        if suffix in {".html", ".css", ".js"}:
            _log(f"web resource changed ({changed_path.name}) -> browser hard reload")
            time.sleep(0.1)
            _trigger_browser_hard_reload_shortcut()
            return

        _log(f"python/runtime changed ({changed_path.name}) -> restarting uvicorn")
        if web_process.poll() is None:
            web_process.terminate()
            try:
                web_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                web_process.kill()
                web_process.wait(timeout=5)
        web_process = spawn_web_process()
        if suffix == ".py":
            time.sleep(0.8)
            _trigger_browser_hot_reload_shortcut()

    observer = Observer()
    handler = RestartOnChangeHandler(restart_callback=restart_web_process)
    for watched_path in watched_paths:
        if watched_path.is_dir():
            observer.schedule(handler, str(watched_path), recursive=True)
        elif watched_path.is_file():
            observer.schedule(handler, str(watched_path.parent), recursive=False)

    observer.start()
    try:
        while True:
            if web_process.poll() is not None:
                web_process = spawn_web_process()
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join(timeout=3)
        if web_process.poll() is None:
            web_process.terminate()
            try:
                web_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                web_process.kill()
