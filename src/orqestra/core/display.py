"""Terminal display — spinner, colors, banner, and department overview.

Provides a rotating spinner that runs in a background thread during
LLM calls and tool execution, plus color helpers for the REPL.
"""

from __future__ import annotations

import itertools
import re
import sys
import threading
from importlib.metadata import PackageNotFoundError, version as _pkg_version
from orqestra._paths import REPO_ROOT
from orqestra.core.departments import DepartmentJob, DepartmentRegistry

_LOGO_PATH = REPO_ROOT / "ascii_logo.txt"
_BANNER_LOGO_LINES: list[str] | None = None


def _read_app_version() -> str:
    """Resolve the app version.

    Prefers ``pyproject.toml`` when the source tree is available (editable
    installs would otherwise return stale ``dist-info`` metadata after a
    version bump without reinstall). Falls back to installed metadata for
    real wheel installs where the source tree is gone.
    """
    pyproject = REPO_ROOT / "pyproject.toml"
    try:
        text = pyproject.read_text(encoding="utf-8")
        m = re.search(r'^\s*version\s*=\s*"([^"]+)"', text, flags=re.MULTILINE)
        if m:
            return m.group(1)
    except OSError:
        pass
    try:
        return _pkg_version("orqestra")
    except PackageNotFoundError:
        return "0.0.0"


APP_VERSION: str = _read_app_version()


def _banner_logo_lines() -> list[str]:
    global _BANNER_LOGO_LINES
    if _BANNER_LOGO_LINES is not None:
        return _BANNER_LOGO_LINES
    if _LOGO_PATH.is_file():
        _BANNER_LOGO_LINES = _LOGO_PATH.read_text(encoding="utf-8").strip().splitlines()
    else:
        _BANNER_LOGO_LINES = ["Orqestra"]
    return _BANNER_LOGO_LINES

# ANSI color codes
DIM = "\033[2m"
BOLD = "\033[1m"
CYAN = "\033[36m"
BLUE = "\033[34m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
MAGENTA = "\033[35m"
RESET = "\033[0m"

_SPINNER_FRAMES = ["|", "/", "—", "\\"]
_SPINNER_INTERVAL = 0.12


class Spinner:
    """Animated spinner that runs in a background thread."""

    def __init__(self, message: str = "Thinking") -> None:
        self._message = message
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self, message: str | None = None) -> None:
        if message:
            self._message = message
        self._stop.clear()
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()

    def update(self, message: str) -> None:
        self._message = message

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1)
            self._thread = None
        sys.stdout.write("\033[2K\r")
        sys.stdout.flush()

    def _spin(self) -> None:
        cycle = itertools.cycle(_SPINNER_FRAMES)
        while not self._stop.is_set():
            frame = next(cycle)
            line = f"  {DIM}{frame} {self._message}{RESET}"
            sys.stdout.write(f"\033[2K\r{line}")
            sys.stdout.flush()
            self._stop.wait(_SPINNER_INTERVAL)

    def __enter__(self) -> Spinner:
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()


_DEPT_ICONS = {
   
}


def print_banner(model: str) -> None:
    """Print the startup banner with ASCII art."""
    logo_lines = _banner_logo_lines()
    info = [
        "",
        f"  {BOLD}Orqestra{RESET} {DIM}v{APP_VERSION}{RESET}",
        f"  {DIM}Orchestrator · Multi-Agent{RESET}",
        "",
        f"  {DIM}Model:{RESET} {model}",
        "",
        "",
    ]
    n = max(len(logo_lines), len(info))
    logo_lines = logo_lines + [""] * (n - len(logo_lines))
    info = info + [""] * (n - len(info))

    col_width = max((len(line) for line in logo_lines), default=0) + 2

    print()
    for f_line, i_line in zip(logo_lines, info):
        padding = " " * max(0, col_width - len(f_line))
        print(f"  {CYAN}{f_line}{RESET}{padding}{i_line}")

    print(
        f"\n{DIM}  /new = new conversation · /status · /stop <id> · /results · exit = quit{RESET}\n"
    )


def print_departments(registry: DepartmentRegistry) -> None:
    """Print departments and their skill counts at startup."""
    if len(registry) == 0:
        return

    print(f"  {DIM}Departments:{RESET}")

    items = registry.items()
    for i, (name, dept) in enumerate(items):
        is_last = i == len(items) - 1
        branch = "└" if is_last else "├"
        icon = _DEPT_ICONS.get(name, "📁")
        skills = dept.skills_summary()
        skill_count = len(skills)
        skill_names = ", ".join(s["name"] for s in skills[:4])
        if skill_count > 4:
            skill_names += f" +{skill_count - 4}"

        print(
            f"  {DIM}{branch}{RESET} {icon} {YELLOW}{dept.label:<20s}{RESET}"
            f"{DIM}{skill_count} skills: {CYAN}{skill_names}{RESET}"
        )

    print()


def format_tool_call(name: str, args_preview: str) -> str:
    """Format a tool call for display."""
    return f"  {DIM}├ {YELLOW}{name}{RESET}{DIM} {args_preview}{RESET}"


def format_response(text: str) -> str:
    """Format the final agent response."""
    separator = f"{CYAN}{'─' * 50}{RESET}"
    return f"\n{separator}\n{text}\n{separator}"


def prompt_string() -> str:
    """Return the styled input prompt."""
    return f"{GREEN}{BOLD}You ▸{RESET} "


def print_job_status(registry: DepartmentRegistry) -> None:
    """Print all tracked department jobs (running and recent)."""
    jobs = registry.jobs_for_display()
    if not jobs:
        print(f"  {DIM}No background jobs.{RESET}\n")
        return

    print(f"  {DIM}Background jobs:{RESET}")
    for j in jobs:
        icon = _DEPT_ICONS.get(j.department, "📁")
        st = j.status()
        st_col = GREEN if st == "done" else YELLOW if st in ("running", "pending") else MAGENTA
        preview = j.task.replace("\n", " ")[:56]
        if len(j.task) > 56:
            preview += "…"
        print(
            f"  {DIM}├{RESET} {icon} {CYAN}{j.id}{RESET} "
            f"{st_col}{st:<10s}{RESET} {DIM}{j.elapsed_seconds():.0f}s{RESET}  {preview}"
        )
    print()


def print_job_notification(job: DepartmentJob) -> None:
    """One-line notice that a background job finished."""
    icon = _DEPT_ICONS.get(job.department, "📁")
    st = job.status()
    print(
        f"\n  {DIM}[background]{RESET} {icon} {YELLOW}{job.id}{RESET} "
        f"{DIM}→{RESET} {st}"
    )


def print_job_result(job: DepartmentJob, *, max_chars: int = 12_000) -> None:
    """Print full result for a completed job."""
    icon = _DEPT_ICONS.get(job.department, "📁")
    st = job.status()
    print(f"\n  {DIM}──{RESET} {icon} {BOLD}{job.id}{RESET} ({st}) {DIM}──{RESET}\n")
    result, err = job.result_or_error()
    if err:
        print(f"  {MAGENTA}{err}{RESET}\n")
        return
    if result is None:
        print(f"  {DIM}(no result yet){RESET}\n")
        return
    text = result if len(result) <= max_chars else result[: max_chars - 80] + "\n\n[… truncated …]"
    print(f"{text}\n")


def print_results_list(registry: DepartmentRegistry, limit: int = 15) -> None:
    """Print summaries of recently completed jobs."""
    done = registry.recent_completed_jobs(limit)
    if not done:
        print(f"  {DIM}No completed jobs yet.{RESET}\n")
        return
    print(f"  {DIM}Recent results (use /results <job_id> for full text):{RESET}")
    for j in done:
        icon = _DEPT_ICONS.get(j.department, "📁")
        result, err = j.result_or_error()
        preview = ""
        if err:
            preview = err[:80]
        elif result:
            one = result.replace("\n", " ")[:72]
            preview = one + ("…" if len(result) > 72 else "")
        print(f"  {DIM}├{RESET} {icon} {CYAN}{j.id}{RESET}  {preview}")
    print()


def notify_finished_jobs(registry: DepartmentRegistry, notified_ids: set[str]) -> None:
    """Print a line for each job that just reached a terminal state."""
    for j in registry.jobs_for_display():
        if j.id in notified_ids:
            continue
        if j.status() in ("done", "cancelled", "error") and (j.future is None or j.future.done()):
            print_job_notification(j)
            notified_ids.add(j.id)
