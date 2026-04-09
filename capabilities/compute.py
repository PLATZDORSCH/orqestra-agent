"""Code execution — run Python scripts in a subprocess.

Allows the agent to perform calculations, data analysis, chart generation,
and report creation programmatically.

Security: Scripts run in a separate subprocess with a timeout.
No network or filesystem restrictions are enforced beyond the timeout
(full sandboxing via seccomp/nsjail would be needed for that).
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import tempfile

from core.capabilities import Capability

log = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 120
_MAX_TIMEOUT = 300
_MAX_STDOUT = 50_000
_MAX_STDERR = 10_000


def _handle_run_script(args: dict) -> str:
    code = args["code"]
    timeout = min(args.get("timeout", _DEFAULT_TIMEOUT), _MAX_TIMEOUT)
    description = args.get("description", "")

    if description:
        log.info("Script execution: %s", description)

    fd, tmp_path = tempfile.mkstemp(suffix=".py", prefix="cod_")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(code)

        proc = subprocess.run(
            [sys.executable, "-u", tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=tempfile.gettempdir(),
            env={
                **os.environ,
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONUNBUFFERED": "1",
            },
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
        "Execute a Python script and return stdout/stderr. "
        "Useful for calculations, data analysis (pandas), charts (matplotlib), "
        "Excel/CSV processing, or any programmatic task. "
        "Available libraries: pandas, matplotlib, openpyxl, requests, json, csv, etc."
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
