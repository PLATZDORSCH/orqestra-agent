"""Proactive mission configuration per department (YAML + runtime)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Mission:
    id: str
    label: str = ""
    prompt: str = ""


@dataclass
class ProactiveConfig:
    """Per-department proactive automation settings.

    Disabled by default — proactive runs are an explicit opt-in per department.
    """

    enabled: bool = False
    schedule: str | None = None  # cron; None = use global fallback from config.yaml
    strategy: str = "rotate"  # rotate | random | all
    missions: list[Mission] = field(default_factory=list)


def parse_proactive_from_dict(raw: dict | None) -> ProactiveConfig | None:
    """Parse ``proactive:`` block from departments.yaml. Returns None if key absent."""
    if raw is None:
        return None
    if not isinstance(raw, dict):
        return ProactiveConfig()
    missions_raw = raw.get("missions") or []
    missions: list[Mission] = []
    for m in missions_raw:
        if not isinstance(m, dict):
            continue
        mid = str(m.get("id") or "").strip()
        if not mid:
            continue
        missions.append(
            Mission(
                id=mid,
                label=str(m.get("label") or mid).strip(),
                prompt=str(m.get("prompt") or "").strip(),
            ),
        )
    strat = str(raw.get("strategy") or "rotate").strip().lower()
    if strat not in ("rotate", "random", "all"):
        strat = "rotate"
    sched = raw.get("schedule")
    schedule = str(sched).strip() if isinstance(sched, str) and sched.strip() else None
    return ProactiveConfig(
        enabled=bool(raw.get("enabled", False)),
        schedule=schedule,
        strategy=strat,
        missions=missions,
    )


def effective_proactive(cfg: ProactiveConfig | None) -> ProactiveConfig:
    """Departments without a ``proactive`` block are disabled by default (opt-in only)."""
    if cfg is None:
        return ProactiveConfig(enabled=False, schedule=None, strategy="rotate", missions=[])
    return cfg
