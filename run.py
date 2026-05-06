import uvicorn
import subprocess
import os
import sys
from pathlib import Path

from app.main import app
from app.config import get_server_host, get_server_port, is_kiosk_mode_enabled, is_qc_mode_enabled
from app.services.smart_web_restarting_daemon import run_smart_web_restarting_daemon

APP_HOST = get_server_host()
APP_PORT = get_server_port()


def find_chrome_executable_path() -> str | None:
    candidate_paths = [
        Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
        Path("C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"),
        Path.home() / "AppData/Local/Google/Chrome/Application/chrome.exe",
    ]
    for candidate_path in candidate_paths:
        if candidate_path.exists():
            return str(candidate_path)
    return None


def launch_debuggable_chrome(admin_dashboard_url: str, kiosk_mode_enabled: bool) -> None:
    chrome_executable_path = find_chrome_executable_path()
    if chrome_executable_path is None:
        return

    user_data_directory_path = Path(__file__).resolve().parent / ".chrome_qc_profile"
    user_data_directory_path.mkdir(parents=True, exist_ok=True)
    chrome_args = [
        chrome_executable_path,
        "--remote-debugging-port=9222",
        f"--user-data-dir={str(user_data_directory_path)}",
        "--disable-save-password-bubble",
        "--disable-features=PasswordManagerOnboarding,PasswordLeakDetection",
    ]
    if kiosk_mode_enabled:
        chrome_args.extend(
            [
                "--kiosk",
            ]
        )
    chrome_args.append(admin_dashboard_url)
    subprocess.Popen(
        chrome_args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        shell=False,
    )


def spawn_uvicorn_process() -> subprocess.Popen:
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            APP_HOST,
            "--port",
            str(APP_PORT),
        ],
        shell=False,
    )


def run_qc_mode_with_watchdog() -> None:
    project_root_path = Path(__file__).resolve().parent
    run_smart_web_restarting_daemon(
        project_root_path=project_root_path,
        spawn_web_process=spawn_uvicorn_process,
    )


def main() -> None:
    qc_mode_enabled = is_qc_mode_enabled()
    kiosk_mode_enabled = is_kiosk_mode_enabled()
    os.environ["QC_MODE"] = "True" if qc_mode_enabled else "False"
    os.environ["KIOSK_MODE"] = "True" if kiosk_mode_enabled else "False"
    os.environ["PRODUCT_TEST_APP_HOST"] = APP_HOST
    os.environ["PRODUCT_TEST_APP_PORT"] = str(APP_PORT)
    if qc_mode_enabled:
        launch_debuggable_chrome(
            f"http://{APP_HOST}:{APP_PORT}/admin",
            kiosk_mode_enabled=False,
        )
        run_qc_mode_with_watchdog()
        return
    uvicorn.run(app, host=APP_HOST, port=APP_PORT)


if __name__ == "__main__":
    main()
