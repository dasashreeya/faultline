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
    ledger_path = cfg.state_dir / "ledger.sqlite3"
    with tempfile.TemporaryDirectory(prefix="faultline-codex-ledger-") as temp_dir:
        backup = Path(temp_dir) / "ledger.sqlite3"
        had_ledger = ledger_path.exists()
        if had_ledger:
            shutil.copy2(ledger_path, backup)
        try:
            try:
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
                    # --ignore-user-config intentionally drops the Windows
                    # workspace-write platform setting along with personal pins.
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
            # Codex verification may run Faultline commands. Overwrite rather
            # than unlink the SQLite file so restoration also works on Windows.
            if had_ledger:
                shutil.copy2(backup, ledger_path)
            else:
                ledger_path.unlink(missing_ok=True)
