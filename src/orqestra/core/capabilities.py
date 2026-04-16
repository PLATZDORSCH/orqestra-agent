"""Capability system for Orqestra.

Each Capability bundles an OpenAI function-calling schema with a handler
function. The CapabilityManager collects them and provides schema export
for the API as well as runtime dispatch.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Callable

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Capability:
    name: str
    description: str
    parameters: dict
    handler: Callable[[dict], str]


class CapabilityManager:
    def __init__(self) -> None:
        self._caps: dict[str, Capability] = {}

    def add(self, cap: Capability) -> None:
        if cap.name in self._caps:
            log.debug("Capability %r is being overwritten", cap.name)
        self._caps[cap.name] = cap

    def remove(self, name: str) -> bool:
        """Remove a capability by name. Returns True if it existed."""
        if name not in self._caps:
            return False
        del self._caps[name]
        return True

    def get(self, name: str) -> Capability | None:
        """Return the capability with *name* or None."""
        return self._caps.get(name)

    def schemas(self) -> list[dict]:
        """Return all capabilities in OpenAI tools format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": c.name,
                    "description": c.description,
                    "parameters": c.parameters,
                },
            }
            for c in self._caps.values()
        ]

    def run(self, name: str, arguments: dict) -> str:
        """Execute a capability and always return JSON."""
        cap = self._caps.get(name)
        if not cap:
            return json.dumps({"error": f"Unknown capability: {name}"}, ensure_ascii=False)
        try:
            return cap.handler(arguments)
        except Exception as exc:
            log.exception("Error in capability %s", name)
            return json.dumps(
                {"error": f"{type(exc).__name__}: {exc}"},
                ensure_ascii=False,
            )

    def names(self) -> list[str]:
        return list(self._caps)

    def __len__(self) -> int:
        return len(self._caps)
