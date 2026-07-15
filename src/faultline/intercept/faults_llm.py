"""F1 · LLM-transport faults — the injection surface below the model.

The tool surface (``adapters/openai_agents.py``) corrupts what tools return.
This module corrupts what the *model endpoint* returns: the 429/500 storms,
context-limit errors, empty completions, truncated answers, mid-stream cutoffs,
and garbage-token bursts that agent frameworks handle terribly. It is the
counterpart to ``faults/library.py`` for the OpenAI wire format.

Design constraints, in priority order:

1. **Pure and deterministic.** Every transform here is a pure function of its
   inputs. The one non-deterministic-looking fault (garbage tokens) is seeded.
   Wall-clock latency is a *declared effect* (:class:`LLMEffect.latency_s`),
   applied by the proxy — never a ``sleep`` inside a transform — so the core
   stays unit-testable without a clock.
2. **Wire-format faithful.** Transforms operate on the exact dict shapes the
   OpenAI Chat Completions API emits, for both non-streaming responses and
   streaming ``chat.completion.chunk`` deltas, so the proxy can apply them to
   real upstream traffic byte-for-byte.
3. **Dependency-free.** No httpx, no server, no SDK. The proxy imports this;
   this imports nothing but the stdlib and the shared :class:`Fault` model.

The proxy consumes exactly one function, :func:`plan_llm_effect`, which reduces
a fault to a small, inspectable description of what to do to the response.
"""

from __future__ import annotations

import copy
import random
from dataclasses import dataclass, field
from typing import Any, Callable

from faultline.faults.library import Fault

# A recognisable, non-language burst. Kept as a marker so gate/anticheat can
# assert a patch never simply string-matches it (same contract as tool markers).
GARBAGE_MARKER = "▓▒░ zxqwv lorem ipsum ░▒▓"


LLM_FAULTS: dict[str, Fault] = {
    f.id: f
    for f in [
        Fault(
            id="llm_server_error",
            fault_class="F1",
            kind="http_error",
            description="Model endpoint returns 500; the call never produces a completion.",
            params={"status": 500, "code": "server_error", "type": "server_error"},
        ),
        Fault(
            id="llm_rate_limit",
            fault_class="F1",
            kind="http_error",
            description="Model endpoint returns 429; a retry storm without backoff makes it worse.",
            params={"status": 429, "code": "rate_limit_exceeded", "type": "rate_limit_error"},
        ),
        Fault(
            id="llm_context_overflow",
            fault_class="F1",
            kind="http_error",
            description="Model endpoint rejects the request as over the context window (400).",
            params={
                "status": 400,
                "code": "context_length_exceeded",
                "type": "invalid_request_error",
            },
        ),
        Fault(
            id="llm_empty_completion",
            fault_class="F1",
            kind="empty",
            description="Model returns a 200 OK with empty assistant content.",
        ),
        Fault(
            id="llm_truncated_response",
            fault_class="F1",
            kind="truncate",
            description="Completion is cut short and flagged finish_reason=length.",
            params={"keep_chars": 24},
        ),
        Fault(
            id="llm_midstream_cutoff",
            fault_class="F1",
            kind="cutoff",
            description="Stream sends a few tokens, then the connection drops with no [DONE].",
            params={"keep_chunks": 3},
        ),
        Fault(
            id="llm_slow_start",
            fault_class="F1",
            kind="latency",
            description="Model stalls before the first token; slow-start stream stresses timeouts.",
            params={"delay_s": 2.0},
        ),
        Fault(
            id="llm_garbage_tokens",
            fault_class="F1",
            kind="garbage",
            description="A burst of garbage tokens is spliced into the model output.",
            marker=GARBAGE_MARKER,
            params={"seed": 0},
        ),
    ]
}


def resolve_llm_fault(fault_id: str) -> Fault | None:
    return LLM_FAULTS.get(fault_id)


def is_llm_fault(fault_id: str) -> bool:
    return fault_id in LLM_FAULTS


# --------------------------------------------------------------------------- #
# Response shape helpers — tolerant of missing keys so a proxy never crashes
# on an unexpected upstream body; it degrades to a no-op instead.
# --------------------------------------------------------------------------- #


def _choices(completion: dict) -> list[dict]:
    choices = completion.get("choices")
    return choices if isinstance(choices, list) else []


def _set_message_content(choice: dict, content: str) -> None:
    message = choice.setdefault("message", {"role": "assistant"})
    message["content"] = content


def _delta_content(chunk: dict) -> str:
    for choice in _choices(chunk):
        delta = choice.get("delta") or {}
        piece = delta.get("content")
        if isinstance(piece, str):
            return piece
    return ""


# --------------------------------------------------------------------------- #
# Non-streaming transforms
# --------------------------------------------------------------------------- #


def empty_completion(completion: dict) -> dict:
    out = copy.deepcopy(completion)
    for choice in _choices(out):
        _set_message_content(choice, "")
        choice["finish_reason"] = "stop"
    return out


def truncate_completion(completion: dict, keep_chars: int) -> dict:
    out = copy.deepcopy(completion)
    keep = max(0, int(keep_chars))
    for choice in _choices(out):
        message = choice.get("message") or {}
        content = message.get("content")
        if isinstance(content, str) and len(content) > keep:
            _set_message_content(choice, content[:keep])
            choice["finish_reason"] = "length"
    return out


def garbage_completion(completion: dict, seed: int) -> dict:
    out = copy.deepcopy(completion)
    rng = random.Random(seed)
    for choice in _choices(out):
        message = choice.get("message") or {}
        content = message.get("content")
        if isinstance(content, str):
            _set_message_content(choice, _splice_garbage(content, rng))
    return out


def _splice_garbage(content: str, rng: random.Random) -> str:
    """Insert the garbage burst at a seeded position inside the content."""
    if not content:
        return GARBAGE_MARKER
    cut = rng.randint(0, len(content))
    return content[:cut] + " " + GARBAGE_MARKER + " " + content[cut:]


# --------------------------------------------------------------------------- #
# Streaming transforms — return (chunks, closed_cleanly). closed_cleanly=False
# means the proxy must drop the connection WITHOUT sending `data: [DONE]`,
# which is exactly what a mid-stream cutoff looks like on the wire.
# --------------------------------------------------------------------------- #


def empty_stream(chunks: list[dict]) -> tuple[list[dict], bool]:
    template = chunks[0] if chunks else {"object": "chat.completion.chunk", "choices": [{"index": 0}]}
    stop = copy.deepcopy(template)
    for choice in _choices(stop):
        choice["delta"] = {}
        choice["finish_reason"] = "stop"
    return [stop], True


def truncate_stream(chunks: list[dict], keep_chars: int) -> tuple[list[dict], bool]:
    keep = max(0, int(keep_chars))
    out: list[dict] = []
    accumulated = 0
    for chunk in chunks:
        piece = _delta_content(chunk)
        if accumulated >= keep and piece:
            break
        out.append(copy.deepcopy(chunk))
        accumulated += len(piece)
        if accumulated >= keep and piece:
            break
    if out:
        for choice in _choices(out[-1]):
            choice["finish_reason"] = "length"
    return out, True


def cutoff_stream(chunks: list[dict], keep_chunks: int) -> tuple[list[dict], bool]:
    keep = max(0, int(keep_chunks))
    return [copy.deepcopy(c) for c in chunks[:keep]], False


def garbage_stream(chunks: list[dict], seed: int) -> tuple[list[dict], bool]:
    if not chunks:
        return chunks, True
    out = [copy.deepcopy(c) for c in chunks]
    rng = random.Random(seed)
    insert_at = rng.randint(0, len(out))
    burst = copy.deepcopy(out[0])
    for choice in _choices(burst):
        choice["delta"] = {"content": " " + GARBAGE_MARKER + " "}
        choice["finish_reason"] = None
    out.insert(insert_at, burst)
    return out, True


# --------------------------------------------------------------------------- #
# The single interface the proxy uses.
# --------------------------------------------------------------------------- #


@dataclass
class LLMEffect:
    """A reduced, inspectable description of what to do to a model response.

    The proxy applies these in a fixed order: wait ``latency_s``; if
    ``http_error`` is set, short-circuit with it and never forward; otherwise
    forward, then apply ``transform_completion`` (non-streaming) or
    ``transform_stream`` (streaming). At most one transform is set.
    """

    latency_s: float = 0.0
    http_error: tuple[int, dict] | None = None
    transform_completion: Callable[[dict], dict] | None = None
    transform_stream: Callable[[list[dict]], tuple[list[dict], bool]] | None = None
    fault_id: str = ""
    fault_class: str = ""
    notes: dict[str, Any] = field(default_factory=dict)


def _error_body(fault: Fault) -> dict:
    params = fault.params
    return {
        "error": {
            "message": fault.description,
            "type": params.get("type", "server_error"),
            "code": params.get("code"),
            "param": None,
        }
    }


def plan_llm_effect(fault: Fault) -> LLMEffect:
    """Reduce an LLM fault to the effect the proxy should apply.

    Unknown or non-LLM faults reduce to a no-op effect, so a mis-scheduled
    fault degrades to a passthrough rather than breaking live traffic.
    """
    effect = LLMEffect(fault_id=fault.id, fault_class=fault.fault_class)
    kind = fault.kind

    if kind == "http_error":
        effect.http_error = (int(fault.params.get("status", 500)), _error_body(fault))
        return effect
    if kind == "latency":
        effect.latency_s = float(fault.params.get("delay_s", 0.0))
        return effect
    if kind == "empty":
        effect.transform_completion = empty_completion
        effect.transform_stream = empty_stream
        return effect
    if kind == "truncate":
        keep = int(fault.params.get("keep_chars", 24))
        effect.transform_completion = lambda c: truncate_completion(c, keep)
        effect.transform_stream = lambda cs: truncate_stream(cs, keep)
        effect.notes["keep_chars"] = keep
        return effect
    if kind == "cutoff":
        keep = int(fault.params.get("keep_chunks", 3))
        # A cutoff has no meaning for a non-streaming call; the closest faithful
        # analogue is a truncated body, so we degrade to that.
        effect.transform_completion = lambda c: truncate_completion(c, 0)
        effect.transform_stream = lambda cs: cutoff_stream(cs, keep)
        effect.notes["keep_chunks"] = keep
        return effect
    if kind == "garbage":
        seed = int(fault.params.get("seed", 0))
        effect.transform_completion = lambda c: garbage_completion(c, seed)
        effect.transform_stream = lambda cs: garbage_stream(cs, seed)
        return effect

    return effect  # no-op for anything we don't recognise
