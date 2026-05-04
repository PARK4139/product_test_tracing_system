import uvicorn
from pathlib import Path
import subprocess
import os
import sys

from app.main import app
from app.services.smart_web_restarting_daemon import run_smart_web_restarting_daemon


def load_bool_mode_from_parent_env(env_key: str, default_value: bool = True) -> bool:
    project_root_path = Path(__file__).resolve().parent
    parent_env_file_path = project_root_path.parent / ".env"

    if not parent_env_file_path.exists():
        parent_env_file_path.write_text(
            "QC_MODE=True\nKIOSK_MODE=True\n",
            encoding="utf-8",
        )
        return default_value

    env_lines = parent_env_file_path.read_text(encoding="utf-8").splitlines()
    found = False
    for env_line in env_lines:
        stripped_line = env_line.strip()
        if not stripped_line or stripped_line.startswith("#") or "=" not in stripped_line:
            continue
        key, value = stripped_line.split("=", 1)
        if key.strip() == env_key:
            found = True
            normalized_value = value.strip().strip('"').strip("'").lower()
            return normalized_value in {"1", "true", "yes", "on"}
    if not found:
        with parent_env_file_path.open("a", encoding="utf-8") as env_file:
            env_file.write(f"\n{env_key}={'True' if default_value else 'False'}\n")
    return default_value


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
            "127.0.0.1",
            "--port",
            "8000",
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
    qc_mode_enabled = load_bool_mode_from_parent_env("QC_MODE", default_value=True)
    kiosk_mode_enabled = load_bool_mode_from_parent_env("KIOSK_MODE", default_value=True)
    os.environ["QC_MODE"] = "True" if qc_mode_enabled else "False"
    os.environ["KIOSK_MODE"] = "True" if kiosk_mode_enabled else "False"
    if qc_mode_enabled:
        launch_debuggable_chrome(
            "http://127.0.0.1:8000/login",
            kiosk_mode_enabled=False,
        )
        run_qc_mode_with_watchdog()
        return
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
