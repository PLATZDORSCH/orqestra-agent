"""Code execution — run Python scripts in a sandboxed subprocess.

Allows the agent to perform calculations, data analysis, chart generation,
and report creation programmatically.

Security layers:
  - Sanitized environment (only safe env vars forwarded)
  - Working directory restricted to a temp folder
  - Timeout per execution (default 120s, max 300s)
  - stdout/stderr size caps
  - Resource limits on memory (512 MB) and CPU time via the subprocess wrapper
"""

from __future__ import annotations

import json
import logging
import os
import resource
import subprocess
import sys
import tempfile

from orqestra.core.capabilities import Capability

log = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 120
_MAX_TIMEOUT = 300
_MAX_STDOUT = 50_000
_MAX_STDERR = 10_000

_MAX_MEMORY_BYTES = 512 * 1024 * 1024  # 512 MB
_MAX_CPU_SECONDS = 300

_SAFE_ENV_KEYS = frozenset({
    "PATH", "HOME", "LANG", "LC_ALL", "LC_CTYPE", "TERM",
    "TMPDIR", "TEMP", "TMP",
    "VIRTUAL_ENV", "CONDA_PREFIX",
    "PYTHONPATH", "PYTHONHOME",
})


def _build_safe_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k in _SAFE_ENV_KEYS}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    return env


def _set_resource_limits() -> None:
    """Called in the child process via preexec_fn to enforce resource limits."""
    try:
        resource.setrlimit(resource.RLIMIT_AS, (_MAX_MEMORY_BYTES, _MAX_MEMORY_BYTES))
    except (ValueError, resource.error):
        pass
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (_MAX_CPU_SECONDS, _MAX_CPU_SECONDS))
    except (ValueError, resource.error):
        pass


def _handle_run_script(args: dict) -> str:
    code = args["code"]
    timeout = min(args.get("timeout", _DEFAULT_TIMEOUT), _MAX_TIMEOUT)
    description = args.get("description", "")

    if description:
        log.info("Script execution: %s", description)

    fd, tmp_path = tempfile.mkstemp(suffix=".py", prefix="orqestra_")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(code)

        proc = subprocess.run(
            [sys.executable, "-u", "-I", tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=tempfile.gettempdir(),
            env=_build_safe_env(),
            preexec_fn=_set_resource_limits,
        )

        stdout = proc.stdout[:_MAX_STDOUT] if proc.stdout else ""
        stderr = proc.stderr[:_MAX_STDERR] if proc.stderr else ""

        return json.dumps({
            "stdout": stdout,
            "stderr": stderr,
            "returncode": proc.returncode,
        }, ensure_ascii=False)

    except subprocess.TimeoutExpired:
        return json.dumps({
            "error": f"Script was terminated after {timeout} seconds",
            "timeout": timeout,
        }, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({
            "error": f"Execution error: {type(exc).__name__}: {exc}",
        }, ensure_ascii=False)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


run_script = Capability(
    name="run_script",
    description=(
        "Execute a Python script in a sandboxed subprocess and return stdout/stderr. "
        "Useful for calculations, data analysis (pandas), charts (matplotlib), "
        "Excel/CSV processing, or any programmatic task. "
        "Available libraries: pandas, matplotlib, openpyxl, requests, json, csv, etc. "
        "Security: sanitized env, memory limit (512 MB), CPU timeout, isolated mode."
    ),
    parameters={
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "Python source code to execute"},
            "description": {"type": "string", "description": "Brief description of what the script does"},
            "timeout": {"type": "integer", "description": f"Timeout in seconds (default: {_DEFAULT_TIMEOUT}, max: {_MAX_TIMEOUT})"},
        },
        "required": ["code"],
    },
    handler=_handle_run_script,
)
