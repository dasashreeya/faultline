from faultline.faults.library import EXFILTRATION_INSTRUCTION, INJECTED_INSTRUCTION
from faultline.gate.anticheat import scan_patch


def test_marker_anticheat_rejects_injected_instruction_literal():
    diff = f"+NOTE = {INJECTED_INSTRUCTION!r}"
    violations = scan_patch(diff)
    assert violations == ["patch hard-codes the injected marker for 'injected_instruction'"]


def test_marker_anticheat_covers_exfiltration_marker():
    diff = f"+NOTE = {EXFILTRATION_INSTRUCTION!r}"
    violations = scan_patch(diff)
    assert violations == ["patch hard-codes the injected marker for 'exfiltration_instruction'"]


def test_marker_anticheat_allows_general_fix():
    diff = "+if is_untrusted_tool_note(note):\n+    continue"
    assert scan_patch(diff) == []
