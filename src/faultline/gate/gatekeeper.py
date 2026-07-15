"""Patch acceptance: golden traces pass AND anti-cheat pass AND score
improves — otherwise the working tree is reverted. Discarded attempts stay
in the ledger; honesty in the report is a feature.
"""

import importlib
import subprocess
import sys

from faultline.config import Config
from faultline.gate.anticheat import scan_patch
from faultline.gate.golden import happy_path_ok
from faultline.ledger.store import Ledger


def _git(cfg: Config, *args: str) -> str:
    out = subprocess.run(
        ["git", "-C", str(cfg.root), *args], capture_output=True, text=True, check=False
    )
    return out.stdout


def revert_worktree(cfg: Config) -> None:
    subprocess.run(["git", "-C", str(cfg.root), "checkout", "--", "."], check=False)


def refresh_target_imports(cfg: Config) -> None:
    """Make the gate execute the patch on disk, not pre-patch cached modules."""
    entrypoints = (
        getattr(cfg, "agent_entrypoint", ""),
        getattr(cfg, "tools_entrypoint", ""),
        getattr(cfg, "reset_entrypoint", ""),
        getattr(cfg, "snapshot_entrypoint", ""),
    )
    modules = {entrypoint.partition(":")[0] for entrypoint in entrypoints if entrypoint}
    prefixes = {module.rpartition(".")[0] or module for module in modules}
    for loaded in list(sys.modules):
        if any(loaded == prefix or loaded.startswith(prefix + ".") for prefix in prefixes):
            sys.modules.pop(loaded, None)
    importlib.invalidate_caches()


async def evaluate_patch(
    cfg: Config, ledger: Ledger, attempt: int, prev_rs: float, summary: str
) -> tuple[bool, str, float]:
    """Run the three gates against the current (patched) working tree.
    Returns (accepted, reason, new_rs). Reverts the tree on rejection."""
    from faultline.run.gauntlet import run_gauntlet

    refresh_target_imports(cfg)
    ok, why = await happy_path_ok(cfg)
    if not ok:
        revert_worktree(cfg)
        return False, f"golden-trace gate: {why}", prev_rs

    violations = scan_patch(_git(cfg, "diff"), model=cfg.judge_model)
    if violations:
        revert_worktree(cfg)
        return False, "anti-cheat gate: " + "; ".join(violations), prev_rs

    new_rs, _ = await run_gauntlet(cfg, attempt)
    if new_rs <= prev_rs:
        revert_worktree(cfg)
        return False, f"improvement gate: score did not improve {prev_rs} → {new_rs}", prev_rs

    subprocess.run(["git", "-C", str(cfg.root), "add", "-A"], check=False)
    subprocess.run(
        ["git", "-C", str(cfg.root), "commit", "-q", "-m", f"harden: {summary}"], check=False
    )
    return True, f"accepted: {prev_rs} → {new_rs}", new_rs
