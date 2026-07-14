"""faultline.yaml loading + entrypoint resolution."""

import importlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class Config:
    root: Path
    agent_entrypoint: str  # "module.path:async_fn(task, tools, model) -> str"
    tools_entrypoint: str  # "module.path:fn(db_path) -> dict[name, callable]"
    reset_entrypoint: str  # "module.path:fn(db_path) -> None"
    snapshot_entrypoint: str  # "module.path:fn(db_path) -> dict"
    scenarios_path: Path
    seeds: list[int] = field(default_factory=lambda: [1, 2])
    judge_mode: str = "detectors"  # detectors | llm
    judge_model: str = "gpt-5.6"
    agent_model: str | None = None
    gate_min_score: float = 85.0
    max_attempts: int = 3
    run_timeout_s: float = 60.0
    isolation: str = "asyncio"  # asyncio | subprocess
    state_dir: Path = field(init=False)

    def __post_init__(self):
        self.state_dir = self.root / ".faultline"
        self.state_dir.mkdir(exist_ok=True)


def load_config(root: Path) -> Config:
    raw: dict[str, Any] = yaml.safe_load((root / "faultline.yaml").read_text(encoding="utf-8"))
    target, judge, harden = raw["target"], raw.get("judge", {}), raw.get("harden", {})
    return Config(
        root=root,
        agent_entrypoint=target["agent"],
        tools_entrypoint=target["tools"],
        reset_entrypoint=target["reset"],
        snapshot_entrypoint=target["snapshot"],
        scenarios_path=root / target["scenarios"],
        seeds=raw.get("seeds", [1, 2]),
        judge_mode=judge.get("mode", "detectors"),
        judge_model=judge.get("model", "gpt-5.6"),
        agent_model=target.get("model"),
        gate_min_score=raw.get("gate", {}).get("min_score", 85.0),
        max_attempts=harden.get("max_attempts", 3),
        run_timeout_s=raw.get("run_timeout_s", 60.0),
        isolation=raw.get("isolation", "asyncio"),
    )


def load_scenarios(path: Path) -> list[dict]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))["scenarios"]


def resolve(entrypoint: str):
    """'pkg.mod:attr' -> the attr."""
    mod_name, _, attr = entrypoint.partition(":")
    return getattr(importlib.import_module(mod_name), attr)
