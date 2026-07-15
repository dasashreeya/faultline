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
    # Codex may stage files. Reset both the index and worktree so a rejected
    # patch cannot remain partially applied or evade the next diff scan.
    subprocess.run(["git", "-C", str(cfg.root), "reset", "--hard", "HEAD"], check=False)


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

    def reject(reason: str) -> tuple[bool, str, float]:
        revert_worktree(cfg)
        if ledger is not None:
            ledger.discard_attempt(attempt)
        return False, reason, prev_rs

    ok, why = await happy_path_ok(cfg)
    if not ok:
        return reject(f"golden-trace gate: {why}")

    violations = scan_patch(_git(cfg, "diff", "HEAD"), model=cfg.judge_model)
    if violations:
        return reject("anti-cheat gate: " + "; ".join(violations))

    new_rs, _ = await run_gauntlet(cfg, attempt)
    if new_rs <= prev_rs:
        return reject(f"improvement gate: score did not improve {prev_rs} → {new_rs}")

    add_result = subprocess.run(["git", "-C", str(cfg.root), "add", "-A"], check=False)
    if getattr(add_result, "returncode", 0) != 0:
        return reject("commit gate: git add failed")
    commit_result = subprocess.run(
        ["git", "-C", str(cfg.root), "commit", "-q", "-m", f"harden: {summary}"], check=False
    )
    if getattr(commit_result, "returncode", 0) != 0:
        return reject("commit gate: git commit failed")
    return True, f"accepted: {prev_rs} → {new_rs}", new_rs
