"""The Hardener: headless `codex exec` against the target repo. THE project.

Sandboxed workspace-write, structured output via --output-schema so the loop
parses results without scraping. `--ignore-user-config` keeps a developer's
personal model pin from breaking the run (auth is unaffected).
"""

import json
import shutil
import subprocess
import sys
import tempfile
from importlib import resources
from pathlib import Path

from jinja2 import Template

from faultline.config import Config

CODEX_TIMEOUT_S = 900


def _prompt_template() -> Template:
    text = (resources.files("faultline.harden") / "prompts" / "hardener_prompt.md").read_text(
        encoding="utf-8"
    )
    return Template(text)


def render_prompt(dossier: dict) -> str:
    return _prompt_template().render(**dossier)


def _schema_path(cfg: Config) -> Path:
    """Materialize the patch_result schema next to the ledger so codex can read it."""
    src = resources.files("faultline.harden") / "patch_result.schema.json"
    dst = cfg.state_dir / "patch_result.schema.json"
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return dst


def run_codex(cfg: Config, dossier: dict) -> dict | None:
    """One hardening attempt. Returns the parsed PatchResult, or None on failure."""
    out_file = cfg.state_dir / "codex_last_message.json"
    out_file.unlink(missing_ok=True)
    cmd = [
        "codex",
        "exec",
        "-C",
        str(cfg.root),
        "--ignore-user-config",
    ]
    if sys.platform == "win32":
        # The Windows workspace-write sandbox is selected by this platform
        # setting. --ignore-user-config intentionally drops personal model
        # pins, but without restoring this one setting Codex silently falls
        # back to read-only and returns a structured no-op patch.
        cmd.extend(["-c", 'windows.sandbox="elevated"'])
    cmd.extend(
        [
            "--sandbox",
            "workspace-write",
            "--skip-git-repo-check",
            "--output-schema",
            str(_schema_path(cfg)),
            "-o",
            str(out_file),
            render_prompt(dossier),
        ]
    )
    ledger_path = cfg.state_dir / "ledger.sqlite3"
    with tempfile.TemporaryDirectory(prefix="faultline-codex-ledger-") as temp_dir:
        backup = Path(temp_dir) / "ledger.sqlite3"
        had_ledger = ledger_path.exists()
        if had_ledger:
            shutil.copy2(ledger_path, backup)
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=CODEX_TIMEOUT_S,
            )
        except subprocess.TimeoutExpired:
            return None
        finally:
            # Codex is required to execute the failing scenario, but those
            # verification commands must not rewrite the parent hardening
            # attempt's runs or score. Restore the ledger after the subprocess
            # exits; the structured response and source diff remain intact.
            for suffix in ("", "-wal", "-shm", "-journal"):
                Path(str(ledger_path) + suffix).unlink(missing_ok=True)
            if had_ledger:
                shutil.copy2(backup, ledger_path)
    if not out_file.exists():
        (cfg.state_dir / "codex_last_error.log").write_text(
            proc.stdout + proc.stderr, encoding="utf-8"
        )
        return None
    try:
        return json.loads(out_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
