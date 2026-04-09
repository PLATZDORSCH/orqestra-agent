"""Terminal display — spinner, colors, and banner.

Provides a rotating spinner that runs in a background thread during
LLM calls and tool execution, plus color helpers for the REPL.
"""

from __future__ import annotations

import itertools
import sys
import threading
import time

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
        sys.stdout.write("\r" + " " * 60 + "\r")
        sys.stdout.flush()

    def _spin(self) -> None:
        cycle = itertools.cycle(_SPINNER_FRAMES)
        while not self._stop.is_set():
            frame = next(cycle)
            line = f"  {DIM}{frame} {self._message}{RESET}"
            pad = max(0, 60 - len(self._message) - 6)
            sys.stdout.write(f"\r{line}{' ' * pad}")
            sys.stdout.flush()
            self._stop.wait(_SPINNER_INTERVAL)

    def __enter__(self) -> Spinner:
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()


def print_banner(model: str) -> None:
    """Print the startup banner with ASCII cod fish."""
    W = "\033[97m"

    fish = [
        r"              _,._",
        r"        _.--''  °  ``--.",
        r"   _.--''                ``--.._",
        r"  (                             )===>",
        r"   ``--.                _.--''",
        r"        ``--..____..--''",
    ]

    info = [
        "",
        f"  {BOLD}Cod Agent{RESET}",
        f"  {DIM}Business Consultant{RESET}",
        "",
        f"  {DIM}Model:{RESET} {model}",
        "",
    ]

    col_width = 42

    print()
    for i, (f_line, i_line) in enumerate(zip(fish, info)):
        padding = " " * max(0, col_width - len(f_line))
        if i == 1:
            colored = f_line.replace("°", f"{W}°{CYAN}")
        else:
            colored = f_line
        print(f"  {CYAN}{colored}{RESET}{padding}{i_line}")

    print(f"\n{DIM}  /new = new conversation · exit = quit{RESET}\n")


_SKILL_CATEGORIES = [
    ("Wiki", "wiki"),
    ("Strategy", "strategy"),
    ("Finance", "finance"),
    ("Marketing", "marketing"),
    ("Sales", "sales"),
    ("Operations", "operations"),
    ("Tech", "tech"),
]


def _categorize_skill(tags: list[str]) -> str:
    tag_set = {t.lower() for t in tags}
    for label, key in _SKILL_CATEGORIES:
        if key in tag_set:
            return label
    if tag_set & {"analysis", "frameworks", "competitive-intelligence"}:
        return "Strategy"
    return "Other"


def print_skills(skills: list[dict]) -> None:
    """Print a compact, categorized skill overview at startup."""
    if not skills:
        return

    groups: dict[str, list[str]] = {}
    for s in skills:
        cat = _categorize_skill(s.get("tags", []))
        groups.setdefault(cat, []).append(s["name"])

    ordered = [label for label, _ in _SKILL_CATEGORIES if label in groups]
    for extra in sorted(groups):
        if extra not in ordered:
            ordered.append(extra)

    total = sum(len(v) for v in groups.values())
    print(f"  {DIM}Skills ({total}):{RESET}")

    for i, cat in enumerate(ordered):
        names = groups[cat]
        is_last = i == len(ordered) - 1
        branch = "└" if is_last else "├"
        items = f"{DIM} · {RESET}".join(f"{CYAN}{n}{RESET}" for n in names)
        print(f"  {DIM}{branch} {YELLOW}{cat:<12s}{RESET}{items}")

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
