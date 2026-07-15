"""Target source edits must be visible to the same-process harden loop."""

from faultline.config import resolve


def test_resolve_fresh_reloads_changed_target_module(tmp_path, monkeypatch):
    module = tmp_path / "reload_target.py"
    module.write_text("value = 'before'\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))

    assert resolve("reload_target:value") == "before"
    module.write_text("value = 'after-this-is-a-different-size'\n", encoding="utf-8")

    assert resolve("reload_target:value", fresh=True) == "after-this-is-a-different-size"
