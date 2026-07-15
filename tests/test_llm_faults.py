"""Unit tests for the F1 LLM-transport fault core (intercept/faults_llm.py).

These pin the pure transforms: same input, same output, wire-format faithful,
and never crashing on a malformed upstream body. The proxy tests build on top.
"""

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from faultline.intercept import faults_llm as fl  # noqa: E402


def _completion(content: str) -> dict:
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 5, "completion_tokens": 20, "total_tokens": 25},
    }


def _chunks(pieces: list[str]) -> list[dict]:
    out = []
    for piece in pieces:
        out.append(
            {
                "object": "chat.completion.chunk",
                "choices": [{"index": 0, "delta": {"content": piece}, "finish_reason": None}],
            }
        )
    out.append(
        {"object": "chat.completion.chunk", "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}
    )
    return out


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #


def test_all_llm_faults_are_class_f1():
    assert fl.LLM_FAULTS
    assert all(f.fault_class == "F1" for f in fl.LLM_FAULTS.values())


def test_resolve_and_is_llm_fault():
    assert fl.is_llm_fault("llm_empty_completion")
    assert not fl.is_llm_fault("stale_data")  # a tool fault
    assert fl.resolve_llm_fault("nope") is None


# --------------------------------------------------------------------------- #
# HTTP-error faults short-circuit
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "fault_id,status",
    [("llm_server_error", 500), ("llm_rate_limit", 429), ("llm_context_overflow", 400)],
)
def test_http_error_faults_produce_status_and_openai_error_body(fault_id, status):
    effect = fl.plan_llm_effect(fl.LLM_FAULTS[fault_id])
    assert effect.http_error is not None
    code, body = effect.http_error
    assert code == status
    assert "error" in body and body["error"]["type"]
    # short-circuit faults do not also transform a body
    assert effect.transform_completion is None
    assert effect.transform_stream is None


# --------------------------------------------------------------------------- #
# Latency is a declared effect, not a sleep in the transform
# --------------------------------------------------------------------------- #


def test_latency_fault_declares_delay_and_does_not_transform():
    effect = fl.plan_llm_effect(fl.LLM_FAULTS["llm_slow_start"])
    assert effect.latency_s > 0
    assert effect.http_error is None
    assert effect.transform_completion is None


# --------------------------------------------------------------------------- #
# Empty completion
# --------------------------------------------------------------------------- #


def test_empty_completion_blanks_content():
    out = fl.empty_completion(_completion("the real answer"))
    assert out["choices"][0]["message"]["content"] == ""
    assert out["choices"][0]["finish_reason"] == "stop"


def test_empty_stream_collapses_to_single_stop_chunk():
    chunks, closed = fl.empty_stream(_chunks(["Hel", "lo"]))
    assert closed is True
    assert len(chunks) == 1
    assert chunks[0]["choices"][0]["finish_reason"] == "stop"
    assert chunks[0]["choices"][0]["delta"] == {}


# --------------------------------------------------------------------------- #
# Truncation
# --------------------------------------------------------------------------- #


def test_truncate_completion_cuts_and_flags_length():
    out = fl.truncate_completion(_completion("0123456789abcdef"), keep_chars=4)
    assert out["choices"][0]["message"]["content"] == "0123"
    assert out["choices"][0]["finish_reason"] == "length"


def test_truncate_completion_leaves_short_content_untouched():
    out = fl.truncate_completion(_completion("hi"), keep_chars=99)
    assert out["choices"][0]["message"]["content"] == "hi"
    assert out["choices"][0]["finish_reason"] == "stop"


def test_truncate_stream_stops_after_budget_and_flags_length():
    chunks, closed = fl.truncate_stream(_chunks(["aaaa", "bbbb", "cccc"]), keep_chars=5)
    assert closed is True
    text = "".join(fl._delta_content(c) for c in chunks)
    assert len(text) <= 8  # stopped near the budget, not the full 12 chars
    assert chunks[-1]["choices"][0]["finish_reason"] == "length"


# --------------------------------------------------------------------------- #
# Mid-stream cutoff — the connection drop
# --------------------------------------------------------------------------- #


def test_cutoff_stream_keeps_prefix_and_signals_dirty_close():
    chunks, closed = fl.cutoff_stream(_chunks(["a", "b", "c", "d", "e"]), keep_chunks=2)
    assert closed is False  # proxy must NOT send [DONE]
    assert len(chunks) == 2
    # none of the kept chunks may claim a clean finish
    assert all(c["choices"][0]["finish_reason"] is None for c in chunks)


def test_cutoff_degrades_to_truncation_for_nonstreaming():
    effect = fl.plan_llm_effect(fl.LLM_FAULTS["llm_midstream_cutoff"])
    out = effect.transform_completion(_completion("a full answer"))
    assert out["choices"][0]["finish_reason"] == "length"


# --------------------------------------------------------------------------- #
# Garbage tokens — corrupt but deterministic
# --------------------------------------------------------------------------- #


def test_garbage_completion_is_deterministic_and_injects_marker():
    src = _completion("a clean answer about orders")
    a = fl.garbage_completion(src, seed=0)
    b = fl.garbage_completion(src, seed=0)
    assert a == b
    assert fl.GARBAGE_MARKER in a["choices"][0]["message"]["content"]


def test_garbage_stream_inserts_a_burst_chunk():
    chunks, closed = fl.garbage_stream(_chunks(["clean", " text"]), seed=1)
    assert closed is True
    joined = "".join(fl._delta_content(c) for c in chunks)
    assert fl.GARBAGE_MARKER in joined


# --------------------------------------------------------------------------- #
# Robustness — a malformed upstream body must never crash a transform
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("bad", [{}, {"choices": None}, {"choices": []}, {"choices": [{}]}])
def test_transforms_tolerate_malformed_completions(bad):
    for fault_id in ("llm_empty_completion", "llm_truncated_response", "llm_garbage_tokens"):
        effect = fl.plan_llm_effect(fl.LLM_FAULTS[fault_id])
        assert effect.transform_completion(dict(bad)) is not None


def test_unknown_fault_reduces_to_noop_effect():
    from faultline.faults.library import Fault

    effect = fl.plan_llm_effect(Fault(id="mystery", fault_class="F1", kind="???", description=""))
    assert effect.http_error is None
    assert effect.transform_completion is None
    assert effect.transform_stream is None
    assert effect.latency_s == 0.0
