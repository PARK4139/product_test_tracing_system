import ctypes
import ctypes.wintypes
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable

from app.config import get_server_host, get_server_port
from app.services.logging_service import get_logger
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

_logger = get_logger("smart_web_restarting_daemon")


def _log(message: str) -> None:
    _logger.info("[smart_web_restarting_daemon] %s", message)


# ── SendInput structures (safe to define cross-platform; Win32-only at call time) ──

class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk",         ctypes.wintypes.WORD),
        ("wScan",       ctypes.wintypes.WORD),
        ("dwFlags",     ctypes.wintypes.DWORD),
        ("time",        ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),       # ULONG_PTR: 4B on 32-bit, 8B on 64-bit
    ]


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx",          ctypes.wintypes.LONG),
        ("dy",          ctypes.wintypes.LONG),
        ("mouseData",   ctypes.wintypes.DWORD),
        ("dwFlags",     ctypes.wintypes.DWORD),
        ("time",        ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class _HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg",    ctypes.wintypes.DWORD),
        ("wParamL", ctypes.wintypes.WORD),
        ("wParamH", ctypes.wintypes.WORD),
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", _MOUSEINPUT),     # largest member — sets correct union size
        ("ki", _KEYBDINPUT),
        ("hi", _HARDWAREINPUT),
    ]


class _WIN_INPUT(ctypes.Structure):
    _fields_ = [
        ("type",   ctypes.wintypes.DWORD),
        ("_input", _INPUT_UNION),
    ]


_INPUT_KEYBOARD = 1
_KEYEVENTF_KEYUP = 0x0002
_VK_CONTROL = 0x11
_VK_MENU    = 0x12   # Alt
_VK_SHIFT   = 0x10
_VK_R       = 0x52
_SW_RESTORE = 9

_FOCUS_SETTLE_DELAY_S  = 0.15   # wait after confirmed focus before sending keys
_FOCUS_RETRY_DELAY_S   = 0.10   # wait between focus retry attempts
_MAX_FOCUS_ATTEMPTS    = 3


# ── Low-level helpers ─────────────────────────────────────────────────────────

def _send_key_sequence_via_send_input(vk_down_sequence: list[int]) -> bool:
    """Press all VKs in vk_down_sequence, then release in reverse order via SendInput."""
    if os.name != "nt":
        return False
    try:
        n = len(vk_down_sequence)
        inputs = (_WIN_INPUT * (n * 2))()
        for i, vk in enumerate(vk_down_sequence):
            inputs[i].type = _INPUT_KEYBOARD
            inputs[i]._input.ki.wVk = vk
            inputs[i]._input.ki.dwFlags = 0
        for i, vk in enumerate(reversed(vk_down_sequence)):
            inputs[n + i].type = _INPUT_KEYBOARD
            inputs[n + i]._input.ki.wVk = vk
            inputs[n + i]._input.ki.dwFlags = _KEYEVENTF_KEYUP
        sent = ctypes.windll.user32.SendInput(n * 2, inputs, ctypes.sizeof(_WIN_INPUT))
        return sent == n * 2
    except Exception:
        return False


def _fallback_focus_browser_window_by_title_segments() -> bool:
    """
    Find the best-matching browser window and bring it to the foreground.

    Uses AttachThreadInput to bypass the Windows foreground-lock restriction
    that silently prevents background processes from calling SetForegroundWindow.
    Verifies focus with GetForegroundWindow before returning True.
    """
    if os.name != "nt":
        return False

    app_host = get_server_host()
    app_port = str(get_server_port())
    primary_page_titles = (
        "Product Test Data Tracing System",
        "Product Test",
    )
    exact_window_titles = tuple(
        dict.fromkeys(
            f"{page_title}{chrome_suffix}"
            for page_title in primary_page_titles
            for chrome_suffix in (" - Chrome", " - Google Chrome")
        )
    )
    secondary_title_segments = (
        f"{app_host}:{app_port}",
        "/admin",
        "Chrome",
    )

    try:
        user32  = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        # ── argtypes for type safety / correct calling convention ────────────
        enum_windows_proc_type = ctypes.WINFUNCTYPE(
            ctypes.c_bool,
            ctypes.wintypes.HWND,
            ctypes.wintypes.LPARAM,
        )
        user32.EnumWindows.argtypes             = [enum_windows_proc_type, ctypes.wintypes.LPARAM]
        user32.EnumWindows.restype              = ctypes.c_bool
        user32.IsWindowVisible.argtypes         = [ctypes.wintypes.HWND]
        user32.IsWindowVisible.restype          = ctypes.c_bool
        user32.GetWindowTextLengthW.argtypes    = [ctypes.wintypes.HWND]
        user32.GetWindowTextLengthW.restype     = ctypes.c_int
        user32.GetWindowTextW.argtypes          = [ctypes.wintypes.HWND, ctypes.wintypes.LPWSTR, ctypes.c_int]
        user32.GetWindowTextW.restype           = ctypes.c_int
        user32.ShowWindow.argtypes              = [ctypes.wintypes.HWND, ctypes.c_int]
        user32.ShowWindow.restype               = ctypes.c_bool
        user32.SetForegroundWindow.argtypes     = [ctypes.wintypes.HWND]
        user32.SetForegroundWindow.restype      = ctypes.c_bool
        user32.BringWindowToTop.argtypes        = [ctypes.wintypes.HWND]
        user32.BringWindowToTop.restype         = ctypes.c_bool
        user32.GetForegroundWindow.argtypes     = []
        user32.GetForegroundWindow.restype      = ctypes.wintypes.HWND
        user32.GetWindowThreadProcessId.argtypes = [
            ctypes.wintypes.HWND,
            ctypes.POINTER(ctypes.wintypes.DWORD),
        ]
        user32.GetWindowThreadProcessId.restype = ctypes.wintypes.DWORD
        user32.AttachThreadInput.argtypes       = [
            ctypes.wintypes.DWORD,
            ctypes.wintypes.DWORD,
            ctypes.wintypes.BOOL,
        ]
        user32.AttachThreadInput.restype        = ctypes.wintypes.BOOL
        kernel32.GetCurrentThreadId.argtypes    = []
        kernel32.GetCurrentThreadId.restype     = ctypes.wintypes.DWORD

        # ── enumerate windows, score by title ───────────────────────────────
        best_hwnd_val: int = 0
        best_score: int = -1

        def _enum_windows_proc(hwnd: int, _l_param: int) -> bool:
            nonlocal best_score, best_hwnd_val
            if not user32.IsWindowVisible(hwnd):
                return True
            title_length = user32.GetWindowTextLengthW(hwnd)
            if title_length <= 0:
                return True
            title_buffer = ctypes.create_unicode_buffer(title_length + 1)
            user32.GetWindowTextW(hwnd, title_buffer, title_length + 1)
            title_text = (title_buffer.value or "").strip()
            if not title_text:
                return True

            score = -1
            if title_text in exact_window_titles:
                score = 400
            elif any(
                title_text.endswith(sfx) and pt in title_text
                for pt in primary_page_titles
                for sfx in (" - Chrome", " - Google Chrome")
            ):
                score = 300
            elif any(pt in title_text for pt in primary_page_titles) and "Chrome" in title_text:
                score = 200
            elif all(seg in title_text for seg in secondary_title_segments):
                score = 100

            if score > best_score:
                best_score = score
                best_hwnd_val = hwnd
            return True

        callback = enum_windows_proc_type(_enum_windows_proc)
        user32.EnumWindows(callback, 0)

        if not best_hwnd_val:
            _log("focus: no matching browser window found")
            return False

        _log(f"focus: found browser window score={best_score} hwnd={best_hwnd_val}")
        hwnd = ctypes.wintypes.HWND(best_hwnd_val)

        # 최소화된 경우에만 복원 — 창 크기 변경 방지
        try:
            user32.IsIconic.argtypes = [ctypes.wintypes.HWND]
            user32.IsIconic.restype  = ctypes.wintypes.BOOL
            if user32.IsIconic(hwnd):
                user32.ShowWindow(hwnd, _SW_RESTORE)
        except Exception:
            pass

        # ── AttachThreadInput trick ──────────────────────────────────────────
        # Windows blocks SetForegroundWindow from background processes.
        # Attaching our input queue to the target window's thread grants permission.
        target_tid  = user32.GetWindowThreadProcessId(hwnd, None)
        current_tid = kernel32.GetCurrentThreadId()

        attached = False
        if target_tid and current_tid and target_tid != current_tid:
            attached = bool(user32.AttachThreadInput(current_tid, target_tid, True))

        user32.BringWindowToTop(hwnd)
        sfg_result = user32.SetForegroundWindow(hwnd)

        if attached:
            user32.AttachThreadInput(current_tid, target_tid, False)

        # ── verify focus ─────────────────────────────────────────────────────
        time.sleep(0.05)
        fg_hwnd = user32.GetForegroundWindow()
        if fg_hwnd == best_hwnd_val:
            _log(f"focus: confirmed foreground hwnd={best_hwnd_val}")
            return True

        _log(
            f"focus: SetForegroundWindow={sfg_result} attached={attached} "
            f"fg={fg_hwnd} expected={best_hwnd_val} — trying SwitchToThisWindow"
        )

        # ── fallback: SwitchToThisWindow ─────────────────────────────────────
        try:
            user32.SwitchToThisWindow.argtypes = [ctypes.wintypes.HWND, ctypes.wintypes.BOOL]
            user32.SwitchToThisWindow.restype  = None
            user32.SwitchToThisWindow(hwnd, True)
            time.sleep(0.05)
            fg_hwnd = user32.GetForegroundWindow()
            if fg_hwnd == best_hwnd_val:
                _log("focus: confirmed via SwitchToThisWindow")
                return True
        except Exception:
            pass

        # SetForegroundWindow may have worked even if GetForegroundWindow shows
        # a child-window HWND — treat non-zero return as partial success
        if sfg_result:
            _log("focus: SetForegroundWindow non-zero (unverified) — proceeding")
            return True

        _log("focus: failed to bring window to foreground")
        return False

    except Exception as exc:
        _log(f"focus: exception: {exc}")
        return False


def _fallback_send_ctrl_alt_r() -> bool:
    """Send Ctrl+Alt+R to the focused window via SendInput."""
    if os.name != "nt":
        return False
    return _send_key_sequence_via_send_input([_VK_CONTROL, _VK_MENU, _VK_R])


def _fallback_send_ctrl_shift_r() -> bool:
    """Send Ctrl+Shift+R to the focused window via SendInput."""
    if os.name != "nt":
        return False
    return _send_key_sequence_via_send_input([_VK_CONTROL, _VK_SHIFT, _VK_R])


# ── Reload shortcut dispatchers ───────────────────────────────────────────────

def _trigger_browser_hot_reload_shortcut() -> None:
    used_pk_system_keypress = False
    try:
        from pk_tools.pk_functions.ensure_pressed import ensure_pressed
        used_pk_system_keypress = True
    except Exception:
        used_pk_system_keypress = False

    for attempt in range(_MAX_FOCUS_ATTEMPTS):
        focused = _fallback_focus_browser_window_by_title_segments()
        if not focused:
            _log(f"hot reload: focus attempt {attempt + 1}/{_MAX_FOCUS_ATTEMPTS} failed")
            time.sleep(_FOCUS_RETRY_DELAY_S)
            continue

        # Wait for focus to settle before injecting keystrokes
        time.sleep(_FOCUS_SETTLE_DELAY_S)

        if used_pk_system_keypress:
            try:
                ensure_pressed("ctrl", "alt", "r")
                _log("hot reload sent via pk_system: Ctrl+Alt+R")
                return
            except Exception:
                pass

        if _fallback_send_ctrl_alt_r():
            _log("hot reload sent via SendInput: Ctrl+Alt+R")
            return

        _log(f"hot reload: key send failed on attempt {attempt + 1}")
        time.sleep(0.06)

    _log("failed to send hot reload shortcut after all attempts")


def _trigger_browser_hard_reload_shortcut() -> None:
    used_pk_system_keypress = False
    try:
        from pk_tools.pk_functions.ensure_pressed import ensure_pressed
        used_pk_system_keypress = True
    except Exception:
        used_pk_system_keypress = False

    for attempt in range(_MAX_FOCUS_ATTEMPTS):
        focused = _fallback_focus_browser_window_by_title_segments()
        if not focused:
            _log(f"hard reload: focus attempt {attempt + 1}/{_MAX_FOCUS_ATTEMPTS} failed")
            time.sleep(_FOCUS_RETRY_DELAY_S)
            continue

        time.sleep(_FOCUS_SETTLE_DELAY_S)

        if used_pk_system_keypress:
            try:
                ensure_pressed("ctrl", "shift", "r")
                _log("hard reload sent via pk_system: Ctrl+Shift+R")
                return
            except Exception:
                pass

        if _fallback_send_ctrl_shift_r():
            _log("hard reload sent via SendInput: Ctrl+Shift+R")
            return

        _log(f"hard reload: key send failed on attempt {attempt + 1}")
        time.sleep(0.06)

    _log("failed to send hard reload shortcut after all attempts")


# ── File-change event handler ─────────────────────────────────────────────────

class RestartOnChangeHandler(FileSystemEventHandler):
    def __init__(self, restart_callback: Callable[[list[Path]], None]):
        self.restart_callback = restart_callback
        self._debounce_lock = threading.Lock()
        self._debounce_timer: threading.Timer | None = None
        self._pending_changed_paths: list[Path] = []
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
        src_path   = Path(getattr(event, "src_path", "") or "")
        dest_path_raw = getattr(event, "dest_path", None)
        dest_path  = Path(dest_path_raw) if dest_path_raw else None
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
            self._pending_changed_paths.append(changed_path)
            if self._debounce_timer is not None:
                self._debounce_timer.cancel()
            self._debounce_timer = threading.Timer(0.35, self._flush_pending_changes)
            self._debounce_timer.daemon = True
            self._debounce_timer.start()

    def _flush_pending_changes(self) -> None:
        with self._debounce_lock:
            changed_paths = list(self._pending_changed_paths)
            self._pending_changed_paths.clear()
            self._debounce_timer = None
        if not changed_paths:
            return
        self.restart_callback(list(dict.fromkeys(changed_paths)))


# ── Main daemon entry point ───────────────────────────────────────────────────

def run_smart_web_restarting_daemon(
    project_root_path: Path,
    spawn_web_process: Callable[[], subprocess.Popen],
) -> None:
    watched_paths = [project_root_path]
    web_process = spawn_web_process()

    def restart_web_process(changed_paths: list[Path]) -> None:
        nonlocal web_process
        if not changed_paths:
            return
        normalized_paths = list(dict.fromkeys(changed_paths))
        changed_suffixes = {path.suffix.lower() for path in normalized_paths}
        changed_names = ", ".join(path.name for path in normalized_paths[:5])
        if len(normalized_paths) > 5:
            changed_names = f"{changed_names}, ..."

        if ".py" not in changed_suffixes and changed_suffixes.issubset({".html", ".css", ".js"}):
            _log(f"web resources changed ({changed_names}) -> browser hard reload")
            time.sleep(0.1)
            _trigger_browser_hard_reload_shortcut()
            return

        _log(f"python/runtime changed ({changed_names}) -> restarting uvicorn")
        if web_process.poll() is None:
            web_process.terminate()
            try:
                web_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                web_process.kill()
                web_process.wait(timeout=5)
        web_process = spawn_web_process()
        if ".py" in changed_suffixes:
            time.sleep(0.8)
            _trigger_browser_hot_reload_shortcut()

    observer = Observer()
    handler  = RestartOnChangeHandler(restart_callback=restart_web_process)
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
                web_process.wait(timeout=5)
