"""Anti-cheat: tier 0 = grep the patch for injected marker strings.
A patch that special-cases the marker handled the fault INSTANCE, not the
fault CLASS — reject it. ADD-BACK 1: GPT-5.6 adversarial diff audit.
"""

from faultline.faults.library import TIER0_FAULTS


def scan_patch(diff: str) -> list[str]:
    added = [l for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++")]
    violations = []
    for fault in TIER0_FAULTS.values():
        if fault.marker and any(fault.marker in line for line in added):
            violations.append(f"patch hard-codes the injected marker for '{fault.id}'")
    return violations
