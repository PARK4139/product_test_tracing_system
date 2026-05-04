import re
import subprocess
import sys
import time
from pathlib import Path

from colorama import init as pk_colorma_init

# TODO  .git 있는 디렉토리를 찾아서 root 라고 인지하고 root에서 동작하도록 수정.

pk_colorma_init(autoreset=True)

# 기본 상수
SCRIPT_NAME = Path(__file__).name
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"
DIVIDER = "_______________________________________"

# 전역 스텝 카운터
step_counter = 0


def print_step(description: str):
    global step_counter
    step_counter += 1
    print(f"[{step_counter}] {description}")


def print_status(step, code: int, output: str) -> str:
    if code == 0:
        label, color = "SUCCESS", GREEN
    elif "nothing to commit" in output.lower():
        label, color = "SKIPPED", YELLOW
    elif "everything up-to-date" in output.lower():
        label, color = "SKIPPED", YELLOW
    else:
        label, color = "FAILED", RED
    print(f"{step:<15}: {color}{label}{RESET}")
    return label


def run_command(cmd: str, capture_output=False):
    try:
        if capture_output:
            result = subprocess.run(cmd, shell=True, text=True, capture_output=True, encoding='utf-8', errors='replace')
            return result.returncode, result.stdout + result.stderr
        else:
            result = subprocess.run(cmd, shell=True, encoding='utf-8', errors='replace')
            return result.returncode, ""
    except Exception as e:
        return 1, str(e)


def get_next_commit_number():
    code, log_output = run_command('git log -n 20 --pretty=format:%s', capture_output=True)
    if code != 0:
        return 1
    numbers = []
    for line in log_output.splitlines():
        match = re.match(r"\[(\d+)\]", line)
        if match:
            numbers.append(int(match.group(1)))
    return max(numbers, default=0) + 1


def fail_and_exit(start_time):
    print(f"{RED}[!] Aborting further steps. Current git status:{RESET}")
    _, status_out = run_command("git status", capture_output=True)
    print(status_out.strip())
    duration = time.time() - start_time
    print(f"{RED}process failed at {time.strftime('%Y-%m-%d %H:%M:%S')} (elapsed {duration:.2f} sec){RESET}")
    sys.exit(1)


def _run_main():
    print(DIVIDER)
    start_time = time.time()
    print(f"process started at {time.strftime('%Y-%m-%d %H:%M:%S')}")

    # 1. git add
    print(DIVIDER)
    print_step("git add .")
    code, output = run_command("git add .", capture_output=True)
    print(output.strip())
    status = print_status("git add", code, output)
    if status == "FAILED":
        fail_and_exit(start_time)

    # 2. git commit
    print(DIVIDER)
    print_step("git commit")
    commit_number = get_next_commit_number()
    commit_message = f"msp: make save point by {SCRIPT_NAME}"
    code, output = run_command(f'git commit -m "{commit_message}"', capture_output=True)
    print(output.strip())
    status = print_status("git commit", code, output)
    if status == "FAILED":
        fail_and_exit(start_time)

    # 3. git push
    print(DIVIDER)
    print_step("git push")
    code, output = run_command("git push", capture_output=True)
    print(output.strip())
    status = print_status("git push", code, output)
    print(DIVIDER)

    if any(protocol in output for protocol in ["To https://", "To http://", "To git@"]):
        pass
    elif "everything up-to-date" in output.lower():
        pass
    else:
        fail_and_exit(start_time)

    duration = time.time() - start_time
    print(f"{GREEN}All process completed. Total execution time: {duration:.2f} seconds {RESET}")
    print(DIVIDER)


if __name__ == "__main__":
    # from pk_tools.pk_functions.ensure_pk_system_wrapper_ui_cleanup import ensure_pk_system_wrapper_ui_cleanup
    # ensure_pk_system_wrapper_ui_cleanup(func_to_run=_run_main, traced_file=__file__)
    _run_main()
