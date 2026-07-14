"""Repo digest for the Planner.

The GPT planner should not receive a raw tarball of the repo. It gets a small,
deterministic digest: config, scenarios, source snippets, and a static risk
scan for retry/timeout/idempotency/prompt-injection smells. The same digest is
also useful in heuristic mode because it makes `faultline plan` explainable
without an API key.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

TEXT_SUFFIXES = {".py", ".yaml", ".yml", ".json", ".md", ".toml"}
SKIP_DIRS = {".git", ".faultline", ".venv", "venv", "__pycache__", ".pytest_cache"}
MAX_FILE_CHARS = 12_000
MAX_TOTAL_CHARS = 80_000


def _safe_read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(errors="replace")


def _iter_digest_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel_parts = set(path.relative_to(root).parts)
        if rel_parts & SKIP_DIRS:
            continue
        if path.suffix.lower() in TEXT_SUFFIXES:
            files.append(path)
    return sorted(files, key=lambda p: str(p.relative_to(root)))


def _function_names(source: str) -> list[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.append(node.name)
    return names


def _risk_hints(rel: str, text: str) -> list[str]:
    lower = text.lower()
    hints: list[str] = []
    if "refund" in lower and ("connectionerror" in lower or "except" in lower):
        hints.append(f"{rel}: side-effecting refund path has retry/error handling; check idempotency")
    if "timeout" not in lower and ("httpx." in lower or "requests." in lower):
        hints.append(f"{rel}: outbound call appears to lack an explicit timeout")
    if "ignore previous instructions" in lower or "system override" in lower:
        hints.append(f"{rel}: prompt-injection marker or handling path is present")
    if ".get(\"orders\"" in lower or ".get('orders'" in lower:
        hints.append(f"{rel}: trusts tool result shape for orders")
    if "updated_at" in lower and ("sort" not in lower and "max(" not in lower):
        hints.append(f"{rel}: timestamp freshness is present but may not be validated")
    if "except exception" in lower or "except:" in lower:
        hints.append(f"{rel}: broad exception handling may hide fault semantics")
    return hints


def build_repo_digest(root: Path, scenarios: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Return a compact, deterministic digest suitable for planner prompts."""

    root = root.resolve()
    files = []
    total = 0
    hints: list[str] = []

    for path in _iter_digest_files(root):
        rel = path.relative_to(root).as_posix()
        text = _safe_read(path)
        snippet = text[:MAX_FILE_CHARS]
        if total + len(snippet) > MAX_TOTAL_CHARS:
            snippet = snippet[: max(0, MAX_TOTAL_CHARS - total)]
        if not snippet:
            break
        total += len(snippet)
        entry = {
            "path": rel,
            "chars": len(text),
            "snippet": snippet,
        }
        if path.suffix == ".py":
            entry["functions"] = _function_names(text)
        files.append(entry)
        hints.extend(_risk_hints(rel, text))
        if total >= MAX_TOTAL_CHARS:
            break

    return {
        "root": str(root),
        "scenarios": scenarios or [],
        "files": files,
        "risk_hints": sorted(set(hints)),
    }
