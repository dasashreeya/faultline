"""Tool-surface fault injection (tier 0).

Wraps the target's raw tool callables so every call consults the FaultSchedule
before/after hitting the real tool, and records a transcript. Works below any
framework — the OpenAI Agents SDK builds its function_tools from the wrapped
callables, and the scripted sandbox agent calls them directly.
"""

import functools
import hashlib
import json
import time
from collections import defaultdict
from typing import Callable


class Transcript:
    def __init__(self):
        self.events: list[dict] = []

    def add(self, type: str, **kw) -> None:
        self.events.append({"type": type, **kw})


def _args_hash(kwargs: dict) -> str:
    blob = json.dumps(kwargs, sort_keys=True, default=str)
    return hashlib.sha1(blob.encode()).hexdigest()[:12]


def wrap_tools(
    tools: dict[str, Callable], schedule: dict, transcript: Transcript
) -> dict[str, Callable]:
    from faultline.faults.library import TIER0_FAULTS, mutate_result

    counters: defaultdict[str, int] = defaultdict(int)
    flap_onset: dict[str, int] = {}  # target -> step at which flapping started
    entries = defaultdict(list)
    for e in schedule["entries"]:
        entries[e["target"]].append(e)

    def make(name: str, fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapped(**kwargs):
            step = counters[name]
            counters[name] += 1
            transcript.add("tool_call", tool=name, args_hash=_args_hash(kwargs), content=kwargs)

            entry = next((e for e in entries.get(name, []) if e["step"] == step), None)
            fault = TIER0_FAULTS[entry["fault"]] if entry else None

            # Flapping persists past its onset: every other call keeps failing.
            if fault is None and name in flap_onset and (step - flap_onset[name]) % 2 == 0:
                fault = TIER0_FAULTS["tool_flapping"]

            if fault is None:
                result = fn(**kwargs)
                transcript.add("tool_result", tool=name, content=result)
                return result

            transcript.add("fault_injected", tool=name, fault=fault.id, step=step)

            if fault.kind == "raise_before":
                time.sleep(float(fault.params.get("hang_s", 0)))
                error = fault.params.get("error", "timeout")
                if error == "rate_limit":
                    raise RuntimeError(f"{name}: 429 rate limit")
                if error == "permission":
                    raise PermissionError(f"{name}: permission denied")
                raise TimeoutError(f"{name} timed out")
            if fault.kind == "raise_after":
                flap_onset.setdefault(name, step)
                fn(**kwargs)  # the side effect LANDS; the response is lost
                raise ConnectionError(f"{name}: connection reset by peer")
            result = mutate_result(fault, fn(**kwargs))
            transcript.add("tool_result", tool=name, content=result, corrupted=True)
            return result

        return wrapped

    return {name: make(name, fn) for name, fn in tools.items()}
