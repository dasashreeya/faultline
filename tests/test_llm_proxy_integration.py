"""In-process integration tests for the LLM fault proxy.

The proxy is an ASGI app; a mock upstream is another ASGI app. httpx's
ASGITransport wires them together with no sockets, no network, no API key — the
whole forward-then-inject path runs offline. These tests exercise the transport
end to end; test_llm_faults.py already pins the pure transforms underneath.
"""

import asyncio
import json
import sys
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from faultline.intercept.faults_llm import GARBAGE_MARKER  # noqa: E402
from faultline.intercept.llm_proxy import LLMFaultProxy, encode_sse  # noqa: E402


class MockUpstream:
    """A stand-in OpenAI endpoint. Counts calls so tests can prove that an
    http_error fault short-circuits before the real API is ever touched."""

    def __init__(self, content="the genuine upstream answer", sse_pieces=("Hello", ", ", "world")):
        self.content = content
        self.sse_pieces = sse_pieces
        self.calls = 0

    def _completion(self):
        return {
            "id": "chatcmpl-upstream",
            "object": "chat.completion",
            "choices": [
                {"index": 0, "message": {"role": "assistant", "content": self.content}, "finish_reason": "stop"}
            ],
        }

    def _sse_chunks(self):
        chunks = [
            {"object": "chat.completion.chunk", "choices": [{"index": 0, "delta": {"content": p}, "finish_reason": None}]}
            for p in self.sse_pieces
        ]
        chunks.append(
            {"object": "chat.completion.chunk", "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}
        )
        return chunks

    async def __call__(self, scope, receive, send):
        assert scope["type"] == "http"
        while True:
            msg = await receive()
            if not msg.get("more_body"):
                break
        self.calls += 1
        # Whether this upstream streams is fixed by the class (StreamingUpstream
        # overrides _respond); the proxy decides streaming from the request body.
        await self._respond(scope, send)

    async def _respond(self, scope, send):
        if scope["path"].endswith("/models"):
            body = json.dumps({"object": "list", "data": []}).encode()
            await self._send(send, 200, body, b"application/json")
            return
        body = json.dumps(self._completion()).encode()
        await self._send(send, 200, body, b"application/json")

    async def _send(self, send, status, body, ctype):
        await send({"type": "http.response.start", "status": status, "headers": [(b"content-type", ctype)]})
        await send({"type": "http.response.body", "body": body})


class StreamingUpstream(MockUpstream):
    async def _respond(self, scope, send):
        body = encode_sse(self._sse_chunks(), True)
        await self._send(send, 200, body, b"text/event-stream")


def _factory(upstream):
    def make():
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=upstream), base_url="http://upstream")
    return make


async def _post(proxy, body):
    transport = httpx.ASGITransport(app=proxy)
    async with httpx.AsyncClient(transport=transport, base_url="http://proxy") as client:
        return await client.post("http://proxy/v1/chat/completions", json=body)


def _schedule(*faults_by_step):
    return {
        "scenario_id": "llm-test",
        "seed": 1,
        "entries": [
            {"step": step, "surface": "llm", "target": "llm", "fault": fid}
            for step, fid in faults_by_step
        ],
    }


# --------------------------------------------------------------------------- #


def test_passthrough_when_no_fault_scheduled():
    upstream = MockUpstream()
    proxy = LLMFaultProxy("http://upstream", schedule=None, client_factory=_factory(upstream))
    resp = asyncio.run(_post(proxy, {"model": "gpt-5.6", "messages": []}))
    assert resp.status_code == 200
    assert resp.json()["choices"][0]["message"]["content"] == "the genuine upstream answer"
    assert upstream.calls == 1
    assert proxy.injections == []


def test_http_error_short_circuits_without_touching_upstream():
    upstream = MockUpstream()
    proxy = LLMFaultProxy(
        "http://upstream", schedule=_schedule((0, "llm_rate_limit")), client_factory=_factory(upstream)
    )
    resp = asyncio.run(_post(proxy, {"model": "gpt-5.6", "messages": []}))
    assert resp.status_code == 429
    assert resp.json()["error"]["type"] == "rate_limit_error"
    assert upstream.calls == 0  # the fault fired before we ever forwarded
    assert proxy.injections[0]["fault"] == "llm_rate_limit"


def test_empty_completion_fault_blanks_the_answer():
    upstream = MockUpstream()
    proxy = LLMFaultProxy(
        "http://upstream", schedule=_schedule((0, "llm_empty_completion")), client_factory=_factory(upstream)
    )
    resp = asyncio.run(_post(proxy, {"model": "gpt-5.6", "messages": []}))
    assert resp.status_code == 200
    assert resp.json()["choices"][0]["message"]["content"] == ""
    assert upstream.calls == 1  # forwarded, then mutated


def test_truncated_fault_flags_length():
    upstream = MockUpstream(content="0123456789abcdefghijklmnopqrstuvwxyz0123456789")
    proxy = LLMFaultProxy(
        "http://upstream", schedule=_schedule((0, "llm_truncated_response")), client_factory=_factory(upstream)
    )
    resp = asyncio.run(_post(proxy, {"model": "gpt-5.6", "messages": []}))
    choice = resp.json()["choices"][0]
    assert choice["finish_reason"] == "length"
    assert len(choice["message"]["content"]) <= 24


def test_garbage_fault_injects_marker():
    upstream = MockUpstream()
    proxy = LLMFaultProxy(
        "http://upstream", schedule=_schedule((0, "llm_garbage_tokens")), client_factory=_factory(upstream)
    )
    resp = asyncio.run(_post(proxy, {"model": "gpt-5.6", "messages": []}))
    assert GARBAGE_MARKER in resp.json()["choices"][0]["message"]["content"]


def test_fault_only_fires_on_the_scheduled_step():
    upstream = MockUpstream()
    proxy = LLMFaultProxy(
        "http://upstream", schedule=_schedule((1, "llm_empty_completion")), client_factory=_factory(upstream)
    )
    first = asyncio.run(_post(proxy, {"model": "gpt-5.6", "messages": []}))
    second = asyncio.run(_post(proxy, {"model": "gpt-5.6", "messages": []}))
    assert first.json()["choices"][0]["message"]["content"] == "the genuine upstream answer"
    assert second.json()["choices"][0]["message"]["content"] == ""
    assert [i["fault"] for i in proxy.injections] == ["llm_empty_completion"]


def test_non_chat_paths_pass_through():
    upstream = MockUpstream()
    proxy = LLMFaultProxy(
        "http://upstream", schedule=_schedule((0, "llm_rate_limit")), client_factory=_factory(upstream)
    )

    async def _get_models():
        transport = httpx.ASGITransport(app=proxy)
        async with httpx.AsyncClient(transport=transport, base_url="http://proxy") as client:
            return await client.get("http://proxy/v1/models")

    resp = asyncio.run(_get_models())
    assert resp.status_code == 200
    assert resp.json()["object"] == "list"
    assert proxy.injections == []  # the rate-limit fault must not touch /models


# --------------------------------------------------------------------------- #
# Streaming
# --------------------------------------------------------------------------- #


async def _post_stream(proxy, body):
    transport = httpx.ASGITransport(app=proxy)
    async with httpx.AsyncClient(transport=transport, base_url="http://proxy") as client:
        return await client.post("http://proxy/v1/chat/completions", json=body)


def test_streaming_empty_collapses_and_keeps_done():
    upstream = StreamingUpstream()
    proxy = LLMFaultProxy(
        "http://upstream", schedule=_schedule((0, "llm_empty_completion")), client_factory=_factory(upstream)
    )
    resp = asyncio.run(_post_stream(proxy, {"model": "gpt-5.6", "messages": [], "stream": True}))
    assert resp.status_code == 200
    assert "[DONE]" in resp.text
    assert '"finish_reason": "stop"' in resp.text


def test_streaming_cutoff_drops_done_and_shortens():
    upstream = StreamingUpstream(sse_pieces=("a", "b", "c", "d", "e", "f"))
    proxy = LLMFaultProxy(
        "http://upstream", schedule=_schedule((0, "llm_midstream_cutoff")), client_factory=_factory(upstream)
    )
    resp = asyncio.run(_post_stream(proxy, {"model": "gpt-5.6", "messages": [], "stream": True}))
    assert resp.status_code == 200
    assert "[DONE]" not in resp.text  # a dropped connection has no clean terminator
    assert proxy.injections[0]["closed_cleanly"] is False


def test_determinism_same_schedule_same_injections():
    def run():
        upstream = MockUpstream()
        proxy = LLMFaultProxy(
            "http://upstream",
            schedule=_schedule((0, "llm_garbage_tokens"), (2, "llm_empty_completion")),
            client_factory=_factory(upstream),
        )
        for _ in range(3):
            asyncio.run(_post(proxy, {"model": "gpt-5.6", "messages": []}))
        return [i["fault"] for i in proxy.injections]

    assert run() == run() == ["llm_garbage_tokens", "llm_empty_completion"]
