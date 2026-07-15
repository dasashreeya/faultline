"""LLM-surface interceptor: an OpenAI-compatible fault-injecting proxy.

A live agent points its ``base_url`` at this proxy; the proxy forwards
``/chat/completions`` to the real upstream and mutates the response on the way
back according to a deterministic fault schedule. Every framework that speaks
the OpenAI chat wire format — the OpenAI SDK, LiteLLM, LangChain's ChatOpenAI —
gets F1 faults for free, with no change to the target's business logic.

Faults come from :mod:`faultline.intercept.faults_llm`; this module is only the
transport. It is a hand-rolled ASGI app so the offline install needs no web
framework: ``uvicorn`` is imported lazily only when you actually serve, and the
test suite drives the app in-process through ``httpx.ASGITransport`` with a mock
upstream — no network, no API key, no ports.

Scope: ``/chat/completions`` is the faulted surface (buffered so stream-shape
faults like truncation and mid-stream cutoff are expressible). Every other path
is proxied transparently, so model-list calls and other endpoints still work.
"""

from __future__ import annotations

import json
from typing import Awaitable, Callable
from urllib.parse import urljoin

import httpx

from faultline.intercept.faults_llm import LLMEffect, plan_llm_effect, resolve_llm_fault

DEFAULT_UPSTREAM = "https://api.openai.com"
# Hard cap so a mis-set latency fault can never wedge the proxy indefinitely.
MAX_LATENCY_S = 10.0
# Headers we must not copy verbatim when forwarding.
_HOP_BY_HOP = {"host", "content-length", "connection", "keep-alive", "transfer-encoding"}


class LLMFaultController:
    """Turns an LLM-surface fault schedule into a per-call fault decision.

    The 'step' is the 0-indexed chat-completion request number. Same schedule,
    same sequence of faults — the determinism the harden loop depends on.
    """

    def __init__(self, schedule: dict | None = None):
        entries = (schedule or {}).get("entries", [])
        self._by_step = {
            int(e["step"]): e["fault"]
            for e in entries
            if e.get("surface") == "llm" and "fault" in e
        }
        self._calls = 0

    def next_effect(self) -> LLMEffect | None:
        step = self._calls
        self._calls += 1
        fault_id = self._by_step.get(step)
        if fault_id is None:
            return None
        fault = resolve_llm_fault(fault_id)
        return plan_llm_effect(fault) if fault else None


# --------------------------------------------------------------------------- #
# SSE helpers
# --------------------------------------------------------------------------- #


def parse_sse(text: str) -> list[dict]:
    """Extract JSON chunks from an SSE body, ignoring the [DONE] sentinel."""
    chunks: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        payload = line[len("data:") :].strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            chunks.append(json.loads(payload))
        except json.JSONDecodeError:
            continue
    return chunks


def encode_sse(chunks: list[dict], closed_cleanly: bool) -> bytes:
    body = "".join(f"data: {json.dumps(c)}\n\n" for c in chunks)
    if closed_cleanly:
        body += "data: [DONE]\n\n"
    return body.encode("utf-8")


# --------------------------------------------------------------------------- #
# ASGI plumbing (framework-free)
# --------------------------------------------------------------------------- #


async def _read_body(receive: Callable[[], Awaitable[dict]]) -> bytes:
    body = b""
    while True:
        message = await receive()
        body += message.get("body", b"")
        if not message.get("more_body"):
            break
    return body


async def _send_response(
    send: Callable[[dict], Awaitable[None]],
    status: int,
    body: bytes,
    content_type: str = "application/json",
) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [(b"content-type", content_type.encode())],
        }
    )
    await send({"type": "http.response.body", "body": body})


def _forward_headers(scope_headers: list[tuple[bytes, bytes]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw_key, raw_val in scope_headers:
        key = raw_key.decode().lower()
        if key in _HOP_BY_HOP:
            continue
        out[key] = raw_val.decode()
    return out


class LLMFaultProxy:
    """ASGI application. Construct with the upstream base and a fault schedule.

    ``client_factory`` exists purely for tests: it lets the suite inject an
    ``httpx.AsyncClient`` bound to a mock upstream via ASGITransport, so the
    whole forward+inject path runs with no sockets.
    """

    def __init__(
        self,
        upstream: str = DEFAULT_UPSTREAM,
        schedule: dict | None = None,
        *,
        client_factory: Callable[[], httpx.AsyncClient] | None = None,
        max_latency_s: float = MAX_LATENCY_S,
    ):
        self.upstream = upstream.rstrip("/") + "/"
        self.controller = LLMFaultController(schedule)
        self._client_factory = client_factory
        self.max_latency_s = max_latency_s
        # Every injected fault is recorded here so a caller (or a test) can
        # prove what the proxy did — the LLM-surface analogue of the transcript.
        self.injections: list[dict] = []

    def _client(self) -> httpx.AsyncClient:
        if self._client_factory is not None:
            return self._client_factory()
        return httpx.AsyncClient(timeout=httpx.Timeout(60.0))

    async def __call__(self, scope: dict, receive, send) -> None:
        if scope["type"] != "http":
            return
        path = scope.get("path", "")
        body = await _read_body(receive)
        headers = _forward_headers(scope.get("headers", []))
        url = urljoin(self.upstream, path.lstrip("/"))

        if not path.endswith("/chat/completions") or scope.get("method") != "POST":
            await self._passthrough(scope, url, body, headers, send)
            return

        await self._handle_chat(url, body, headers, send)

    async def _passthrough(self, scope, url, body, headers, send) -> None:
        async with self._client() as client:
            resp = await client.request(
                scope.get("method", "GET"), url, content=body, headers=headers
            )
        await _send_response(
            send,
            resp.status_code,
            resp.content,
            resp.headers.get("content-type", "application/json"),
        )

    async def _handle_chat(self, url, body, headers, send) -> None:
        try:
            request_json = json.loads(body or b"{}")
        except json.JSONDecodeError:
            request_json = {}
        streaming = bool(request_json.get("stream"))

        effect = self.controller.next_effect()

        if effect is not None and effect.latency_s > 0:
            import asyncio

            await asyncio.sleep(min(effect.latency_s, self.max_latency_s))

        if effect is not None and effect.http_error is not None:
            status, error_body = effect.http_error
            self._record(effect, "http_error", streaming)
            await _send_response(send, status, json.dumps(error_body).encode())
            return

        if streaming:
            await self._handle_stream(url, body, headers, send, effect)
        else:
            await self._handle_unary(url, body, headers, send, effect)

    async def _handle_unary(self, url, body, headers, send, effect) -> None:
        async with self._client() as client:
            resp = await client.post(url, content=body, headers=headers)
        if resp.status_code != 200 or effect is None or effect.transform_completion is None:
            await _send_response(
                send, resp.status_code, resp.content, resp.headers.get("content-type", "application/json")
            )
            return
        try:
            completion = resp.json()
        except json.JSONDecodeError:
            await _send_response(send, resp.status_code, resp.content)
            return
        mutated = effect.transform_completion(completion)
        self._record(effect, "completion", streaming=False)
        await _send_response(send, 200, json.dumps(mutated).encode())

    async def _handle_stream(self, url, body, headers, send, effect) -> None:
        async with self._client() as client:
            resp = await client.post(url, content=body, headers=headers)
            raw = resp.text
        if resp.status_code != 200 or effect is None or effect.transform_stream is None:
            await _send_response(
                send,
                resp.status_code,
                resp.content,
                resp.headers.get("content-type", "text/event-stream"),
            )
            return
        chunks = parse_sse(raw)
        mutated, closed_cleanly = effect.transform_stream(chunks)
        self._record(effect, "stream", streaming=True, closed_cleanly=closed_cleanly)
        await _send_response(
            send, 200, encode_sse(mutated, closed_cleanly), content_type="text/event-stream"
        )

    def _record(self, effect: LLMEffect, mode: str, streaming: bool, **extra) -> None:
        self.injections.append(
            {
                "call_index": self.controller._calls - 1,
                "fault": effect.fault_id,
                "fault_class": effect.fault_class,
                "mode": mode,
                "streaming": streaming,
                **extra,
            }
        )


def build_app(upstream: str = DEFAULT_UPSTREAM, schedule: dict | None = None, **kwargs) -> LLMFaultProxy:
    """Convenience constructor mirroring the ASGI-factory convention."""
    return LLMFaultProxy(upstream=upstream, schedule=schedule, **kwargs)


def serve(app: LLMFaultProxy, host: str = "127.0.0.1", port: int = 8787) -> None:
    """Run the proxy with uvicorn. Imported lazily so the offline install is lean."""
    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover - only hit without the extra
        raise RuntimeError(
            "Serving the live LLM proxy needs uvicorn. Install it with "
            "'uv pip install uvicorn' or 'pip install faultline[proxy]'."
        ) from exc
    uvicorn.run(app, host=host, port=port)
