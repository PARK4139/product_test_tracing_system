from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


# TODO : _________________________________________________ 0. CONFIG
NPX_CMD_CANDIDATES = ["npx", "npx.cmd"]
GEMINI_NPX_PACKAGE_NAME = "@google/gemini-cli"

GIT_REMOTE = "origin"


# TODO : _________________________________________________ 1. HELPERS
def run_command(
    args: list[str],
    cwd: Path,
    check: bool = True,
    capture_output: bool = True,
    text: bool = True,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    run_kwargs: dict[str, object] = {
        "args": args,
        "cwd": str(cwd),
        "input": input_text,
        "capture_output": capture_output,
        "text": text,
        "shell": False,
    }
    if text:
        run_kwargs["encoding"] = "utf-8"
        run_kwargs["errors"] = "replace"

    result = subprocess.run(**run_kwargs)
    if check and result.returncode != 0:
        stdout_text = (result.stdout or "").strip()
        stderr_text = (result.stderr or "").strip()
        raise RuntimeError(
            "\n".join(
                [
                    f"Command failed: {' '.join(args)}",
                    f"Return code: {result.returncode}",
                    f"STDOUT:\n{stdout_text}" if stdout_text else "STDOUT: <empty>",
                    f"STDERR:\n{stderr_text}" if stderr_text else "STDERR: <empty>",
                ]
            )
        )
    return result


def find_existing_command(candidates: list[str]) -> str | None:
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return None


def ask_yes_no(prompt: str) -> bool:
    answer = input(f"{prompt} [y/N]: ").strip().lower()
    return answer in {"y", "yes"}


def print_section(title: str) -> None:
    line = "=" * 70
    print()
    print(line)
    print(title)
    print(line)


# TODO : _________________________________________________ 2. GIT HELPERS
def ensure_git_repo(repo_dir: Path) -> None:
    git_cmd = shutil.which("git")
    if not git_cmd:
        raise RuntimeError("git not found in PATH.")

    result = run_command(
        args=["git", "rev-parse", "--is-inside-work-tree"],
        cwd=repo_dir,
        check=True,
    )
    if result.stdout.strip().lower() != "true":
        raise RuntimeError(f"Current directory is not a git repository: {repo_dir}")


def get_git_status_short(repo_dir: Path) -> str:
    result = run_command(
        args=["git", "status", "--short"],
        cwd=repo_dir,
        check=True,
    )
    return result.stdout.strip()


def stage_all_changes(repo_dir: Path) -> None:
    run_command(
        args=["git", "add", "-A"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )


def has_staged_changes(repo_dir: Path) -> bool:
    result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=str(repo_dir),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
    )
    return result.returncode != 0


def get_staged_diff(repo_dir: Path) -> str:
    result = run_command(
        args=["git", "diff", "--cached"],
        cwd=repo_dir,
        check=True,
    )
    return result.stdout or ""


def get_current_branch(repo_dir: Path) -> str:
    result = run_command(
        args=["git", "branch", "--show-current"],
        cwd=repo_dir,
        check=True,
    )
    branch = result.stdout.strip()
    if not branch:
        raise RuntimeError("Failed to detect current branch.")
    return branch


def commit_with_message_file(repo_dir: Path, commit_message_file: Path) -> None:
    run_command(
        args=["git", "commit", "-F", str(commit_message_file)],
        cwd=repo_dir,
        check=True,
    )


def push_current_branch(repo_dir: Path, remote_name: str, branch_name: str) -> None:
    run_command(
        args=["git", "push", remote_name, branch_name],
        cwd=repo_dir,
        check=True,
        capture_output=False,
    )


# TODO : _________________________________________________ 3. GEMINI HELPERS
def build_commit_prompt() -> str:
    return "\n".join(
        [
            "You are generating a git commit message.",
            "",
            "Requirements:",
            "- Return commit message only.",
            "- No markdown.",
            "- No code block.",
            "- First line: concise subject within 72 chars if possible.",
            "- Then blank line.",
            "- Then detailed bullet list explaining key changes.",
            "- Be specific and technical.",
            "- Mention affected behavior, bug fix, refactor scope, or safety implications if relevant.",
            "- Do not invent changes not present in diff.",
            "",
            "Here is the staged git diff:",
            "",
        ]
    )


def generate_commit_message_via_gemini(repo_dir: Path, diff_text: str) -> str:
    npx_cmd = find_existing_command(candidates=NPX_CMD_CANDIDATES)
    if not npx_cmd:
        raise RuntimeError(
            "npx not found in PATH. "
            f"Tried: {', '.join(NPX_CMD_CANDIDATES)}"
        )

    version_check_result = subprocess.run(
        [npx_cmd, GEMINI_NPX_PACKAGE_NAME, "--version"],
        cwd=str(repo_dir),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
    )
    if version_check_result.returncode != 0:
        stdout_text = (version_check_result.stdout or "").strip()
        stderr_text = (version_check_result.stderr or "").strip()
        raise RuntimeError(
            "\n".join(
                [
                    f"Gemini CLI version check failed: {npx_cmd} {GEMINI_NPX_PACKAGE_NAME} --version",
                    f"Return code: {version_check_result.returncode}",
                    f"STDOUT:\n{stdout_text}" if stdout_text else "STDOUT: <empty>",
                    f"STDERR:\n{stderr_text}" if stderr_text else "STDERR: <empty>",
                ]
            )
        )

    prompt_text = build_commit_prompt()

    result = subprocess.run(
        [npx_cmd, GEMINI_NPX_PACKAGE_NAME, "-p", prompt_text],
        cwd=str(repo_dir),
        input=diff_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
    )

    if result.returncode != 0:
        stdout_text = (result.stdout or "").strip()
        stderr_text = (result.stderr or "").strip()
        raise RuntimeError(
            "\n".join(
                [
                    f"Gemini CLI invocation failed: {npx_cmd} {GEMINI_NPX_PACKAGE_NAME} -p",
                    f"Return code: {result.returncode}",
                    f"STDOUT:\n{stdout_text}" if stdout_text else "STDOUT: <empty>",
                    f"STDERR:\n{stderr_text}" if stderr_text else "STDERR: <empty>",
                ]
            )
        )

    commit_message = (result.stdout or "").strip()
    if not commit_message:
        raise RuntimeError("Gemini CLI returned empty commit message.")

    return commit_message


# TODO : _________________________________________________ 4. MAIN FLOW
def main() -> int:
    repo_dir = Path(__file__).resolve().parent

    print_section(title="Repository push by AI agent commit message")
    print(f"Working directory: {repo_dir}")

    ensure_git_repo(repo_dir=repo_dir)

    print_section(title="Current git status before staging")
    status_before = get_git_status_short(repo_dir=repo_dir)
    print(status_before if status_before else "<clean>")

    print_section(title="Stage all changes")
    stage_all_changes(repo_dir=repo_dir)

    if not has_staged_changes(repo_dir=repo_dir):
        print("No staged changes detected after git add -A.")
        return 0

    print_section(title="Collect staged diff")
    diff_text = get_staged_diff(repo_dir=repo_dir)
    if not diff_text.strip():
        print("No staged diff content found.")
        return 0

    print_section(title="Request detailed commit message from Gemini CLI")
    commit_message = generate_commit_message_via_gemini(
        repo_dir=repo_dir,
        diff_text=diff_text,
    )

    print(commit_message)

    if not ask_yes_no(prompt="Proceed with git commit and git push?"):
        print("User cancelled commit/push.")
        return 0

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".txt",
        delete=False,
    ) as temp_file:
        temp_file.write(commit_message)
        temp_commit_message_file = Path(temp_file.name)

    try:
        print_section(title="Git commit")
        commit_with_message_file(
            repo_dir=repo_dir,
            commit_message_file=temp_commit_message_file,
        )

        current_branch = get_current_branch(repo_dir=repo_dir)

        print_section(title=f"Git push to {GIT_REMOTE}/{current_branch}")
        push_current_branch(
            repo_dir=repo_dir,
            remote_name=GIT_REMOTE,
            branch_name=current_branch,
        )
    finally:
        try:
            temp_commit_message_file.unlink(missing_ok=True)
        except Exception:
            pass

    print_section(title="Success")
    print("Commit and push completed successfully.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        raise SystemExit(130)
    except Exception as exc:
        print_section(title="ERROR")
        print(str(exc))
        raise SystemExit(1)
