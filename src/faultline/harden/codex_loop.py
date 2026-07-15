"""The Hardener: headless `codex exec` against the target repo. THE project.

Sandboxed workspace-write, structured output via --output-schema so the loop
parses results without scraping. `--ignore-user-config` keeps a developer's
personal model pin from breaking the run (auth is unaffected).
"""

import json
import shutil
import subprocess
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
    ledger_path = cfg.state_dir / "ledger.sqlite3"
    ledger_existed = ledger_path.exists()
    ledger_backup = None
    if ledger_existed:
        with tempfile.NamedTemporaryFile(prefix="faultline-ledger-", suffix=".sqlite3", delete=False) as f:
            ledger_backup = Path(f.name)
        shutil.copy2(ledger_path, ledger_backup)

    try:
        out_file = cfg.state_dir / "codex_last_message.json"
        out_file.unlink(missing_ok=True)
        cmd = [
            "codex",
            "exec",
            "-C",
            str(cfg.root),
            "--ignore-user-config",
            "--sandbox",
            "workspace-write",
            "--skip-git-repo-check",
            "--output-schema",
            str(_schema_path(cfg)),
            "-o",
            str(out_file),
            render_prompt(dossier),
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=CODEX_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            return None
        if not out_file.exists():
            (cfg.state_dir / "codex_last_error.log").write_text(
                proc.stdout + proc.stderr, encoding="utf-8"
            )
            return None
        try:
            return json.loads(out_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
    finally:
        # Codex is instructed to verify its patch locally and may run Faultline
        # commands that mutate the ledger. Restore the pre-call ledger so those
        # self-checks cannot rewrite the baseline or survival curve.
        if ledger_backup is not None:
            shutil.copy2(ledger_backup, ledger_path)
            ledger_backup.unlink(missing_ok=True)
        else:
            ledger_path.unlink(missing_ok=True)
