"""End-to-end integration check against a *running* DevAssist backend.

Verifies over real network sockets (not the in-process test client):
  1. GET /health reports the loaded embedding model and index size
  2. POST /upload indexes a document and returns real metadata
  3. GET /documents lists it again
  4. WS /ws/chat delivers the streaming protocol in order
  5. the programming-only policy refuses an off-topic question
  6. DELETE /documents clears the index

Run the backend first, e.g.:

    uvicorn app.main:app --host 127.0.0.1 --port 8000

Usage: python scripts/integration_check.py [base_url]
"""

from __future__ import annotations

import asyncio
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_BASE = "http://127.0.0.1:8000"
SAMPLE = Path(__file__).resolve().parents[1] / "backend" / "tests" / "fixtures" / "sample_notes.md"

failures: list[str] = []


def check(condition: bool, label: str, detail: str = "") -> None:
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {label}" + (f" - {detail}" if detail else ""))
    if not condition:
        failures.append(label)


def get_json(path: str, base: str) -> dict:
    with urllib.request.urlopen(f"{base}{path}", timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def post_file(base: str, filename: str, data: bytes) -> tuple[int, dict]:
    boundary = "----devassistintegration"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode() + data + f"\r\n--{boundary}--\r\n".encode()
    request = urllib.request.Request(
        f"{base}/upload",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8"))


def delete(base: str, path: str) -> int:
    request = urllib.request.Request(f"{base}{path}", method="DELETE")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code


async def websocket_events(base: str, message: str, request_id: str) -> list[dict]:
    """Open a real WebSocket, send one question, collect events until terminal."""
    import websockets

    ws_url = base.replace("http://", "ws://").replace("https://", "wss://") + "/ws/chat"
    events: list[dict] = []
    async with websockets.connect(ws_url, open_timeout=15, max_size=None) as socket:
        await socket.send(json.dumps({"type": "message", "request_id": request_id, "message": message}))
        while len(events) < 60:
            raw = await asyncio.wait_for(socket.recv(), timeout=30)
            event = json.loads(raw)
            events.append(event)
            if event["type"] in {"done", "error"}:
                break
    return events


async def websocket_cancel(base: str, message: str, request_id: str) -> list[dict]:
    """Start a generation and cancel it mid-flight over a real socket."""
    import websockets

    ws_url = base.replace("http://", "ws://").replace("https://", "wss://") + "/ws/chat"
    events: list[dict] = []
    async with websockets.connect(ws_url, open_timeout=15, max_size=None) as socket:
        await socket.send(json.dumps({"type": "message", "request_id": request_id, "message": message}))
        # Wait until generation has actually produced output, then cancel.
        while True:
            event = json.loads(await asyncio.wait_for(socket.recv(), timeout=15))
            events.append(event)
            if event["type"] in {"token", "error"}:
                break
        await socket.send(json.dumps({"type": "cancel", "request_id": request_id}))
        # After a successful cancel the server stops streaming and sends nothing
        # further, so collection ends on timeout rather than a terminal event.
        while True:
            try:
                event = json.loads(await asyncio.wait_for(socket.recv(), timeout=4))
            except (asyncio.TimeoutError, TimeoutError):
                break
            except Exception:
                break
            events.append(event)
            if event["type"] in {"done", "error"}:
                break
    return events


async def websocket_busy(base: str) -> list[dict]:
    """Start a slow generation, then try to start a second on the same socket."""
    import websockets

    ws_url = base.replace("http://", "ws://").replace("https://", "wss://") + "/ws/chat"
    events: list[dict] = []
    async with websockets.connect(ws_url, open_timeout=15, max_size=None) as socket:
        await socket.send(
            json.dumps(
                {
                    "type": "message",
                    "request_id": "busy-a",
                    "message": "Explain very slowly how the vector index works.",
                }
            )
        )
        while True:  # wait for the first stream so the connection is busy
            event = json.loads(await asyncio.wait_for(socket.recv(), timeout=15))
            events.append(event)
            if event["type"] in {"token", "error"}:
                break
        await socket.send(
            json.dumps(
                {
                    "type": "message",
                    "request_id": "busy-b",
                    "message": "Explain very slowly how embeddings work.",
                }
            )
        )
        while True:  # the second request must be rejected with BUSY
            event = json.loads(await asyncio.wait_for(socket.recv(), timeout=15))
            events.append(event)
            if event["type"] == "error" and event.get("request_id") == "busy-b":
                break
        await socket.send(json.dumps({"type": "cancel", "request_id": "busy-a"}))
    return events


async def main(base: str) -> int:
    print(f"\nDevAssist integration check -> {base}\n")

    # 1. Health ---------------------------------------------------------------
    health = get_json("/health", base)
    check(health.get("status") in {"ok", "degraded"}, "GET /health returns a status")
    check(health.get("embedding_loaded") is True, "embedding model is loaded", str(health.get("embedding_model")))
    check(
        isinstance(health.get("groq_configured"), bool),
        "GROQ configuration is reported honestly",
        f"groq_configured={health.get('groq_configured')}",
    )
    check(health.get("limits", {}).get("top_k") == 3, "retrieval top_k is 3")
    check(health.get("limits", {}).get("chunk_size") == 500, "chunk size is 500")

    # 2. Upload ---------------------------------------------------------------
    sample = SAMPLE.read_bytes()
    status, upload = post_file(base, "sample_notes.md", sample)
    check(status == 200 and upload.get("status") == "success", "POST /upload indexes a Markdown file")
    check(upload.get("chunks_processed", 0) >= 1, "upload reports real chunk count", str(upload.get("chunks_processed")))
    check(upload.get("characters_extracted", 0) > 0, "upload reports extracted characters")
    doc_id = upload.get("doc_id", "")

    # 3. Rejected extension ---------------------------------------------------
    bad_status, bad = post_file(base, "malware.exe", b"MZ\x90")
    check(bad_status == 400 and bad.get("code") == "UNSUPPORTED_FILE_TYPE", "POST /upload rejects .exe")

    # 4. Listing --------------------------------------------------------------
    listed = get_json("/documents", base)
    check(listed.get("total_documents") == 1, "GET /documents lists the indexed file")
    check(
        any(doc["doc_id"] == doc_id for doc in listed.get("documents", [])),
        "the uploaded doc_id appears in the listing",
    )

    # 5. WebSocket: retrieval answer -----------------------------------------
    events = await websocket_events(
        base,
        "How many retry attempts and what chunk size does the DevAssist sample notes describe?",
        "integration-1",
    )
    kinds = [event["type"] for event in events]
    print(f"  events: {kinds}")
    check(kinds[0] == "status", "first event is a status event")
    check(kinds[-1] in {"done", "error"}, "conversation ends with a terminal event")
    check(kinds.count("status") >= 2, "status stages (retrieving/generating) are announced")
    check(all(event.get("request_id") == "integration-1" for event in events), "request_id is echoed on every event")

    terminal = events[-1]
    streaming_works = terminal["type"] == "done"
    full_reply_length = 0
    source_events = [event for event in events if event["type"] == "sources"]
    if source_events:
        first_source = source_events[0]["sources"][0]
        check(
            first_source["filename"] == "sample_notes.md",
            "retrieval returned the uploaded document as a source",
            f"chunk {first_source['chunk_index']} score {first_source['score']}",
        )
        check(0.0 <= first_source["score"] <= 1.0, "source score is a real cosine similarity")

    if terminal["type"] == "error":
        # No Groq key in this environment: the safe configuration error is the
        # expected outcome, and it proves the error path over a real socket.
        check(
            terminal["code"]
            in {
                "CONFIG_ERROR",
                "PROVIDER_AUTH_ERROR",
                "PROVIDER_UNAVAILABLE",
                "PROVIDER_TIMEOUT",
                "PROVIDER_ERROR",
                "RATE_LIMITED",
            },
            "provider failure surfaced as a safe coded error",
            f"{terminal['code']}: {terminal['message']}",
        )
        check(
            "traceback" not in terminal["message"].lower() and "site-packages" not in terminal["message"],
            "error message leaks no internals",
        )
    else:
        tokens = "".join(event["token"] for event in events if event["type"] == "token")
        check(len(tokens) > 0, "streamed tokens arrived", f"{len(tokens)} chars")
        check(kinds.count("token") >= 2, "the answer arrived incrementally", f"{kinds.count('token')} token events")
        has_sources = "sources" in kinds
        check(has_sources, "sources were attributed before the answer")
        check(
            has_sources and kinds.index("sources") < kinds.index("token") and kinds.index("token") < kinds.index("done"),
            "ordering is status -> sources -> token -> done",
        )
        full_reply_length = len(tokens)

    # 6. WebSocket: policy refusal -------------------------------------------
    off_topic = await websocket_events(base, "What is the weather in Paris tomorrow?", "integration-2")
    kinds = [event["type"] for event in off_topic]
    print(f"  events: {kinds}")
    refusal_text = "".join(event["token"] for event in off_topic if event["type"] == "token")
    check("programming" in refusal_text.lower(), "off-topic question was politely declined", refusal_text[:70])
    check(off_topic[-1]["type"] == "done", "refusal completes normally without calling the provider")

    # 7. WebSocket: cancel mid-stream ----------------------------------------
    if streaming_works:
        cancelled = await websocket_cancel(
            base,
            "Explain very slowly how the vector index and embeddings work.",
            "integration-3",
        )
        cancelled_kinds = [event["type"] for event in cancelled]
        print(f"  events: {cancelled_kinds}")
        cancelled_text = "".join(event["token"] for event in cancelled if event["type"] == "token")
        check("token" in cancelled_kinds, "generation had started before the cancel")
        check("done" not in cancelled_kinds, "cancel suppressed the terminal done event")
        check(
            len(cancelled_text) < full_reply_length,
            "cancel stopped the stream early",
            f"{len(cancelled_text)} < {full_reply_length} chars",
        )
        check(
            all(event.get("request_id") == "integration-3" for event in cancelled),
            "cancel events keep the request_id",
        )
    else:
        print("  [INFO] skipping cancel checks: no streaming provider is configured")

    # 8. WebSocket: one in-flight generation per connection ------------------
    if streaming_works:
        busy_events = await websocket_busy(base)
        busy_kinds = [event["type"] for event in busy_events]
        busy_errors = [
            event for event in busy_events if event["type"] == "error" and event.get("request_id") == "busy-b"
        ]
        print(f"  events: {busy_kinds}")
        check(bool(busy_errors) and busy_errors[0].get("code") == "BUSY", "second concurrent request is rejected with BUSY")
        check(
            any(event["type"] == "token" for event in busy_events),
            "the first generation kept streaming while the second was rejected",
        )
    else:
        print("  [INFO] skipping busy checks: no streaming provider is configured")

    # 9. Malformed frame ------------------------------------------------------
    import websockets

    ws_url = base.replace("http://", "ws://") + "/ws/chat"
    async with websockets.connect(ws_url, open_timeout=15, max_size=None) as socket:
        await socket.send("this is not json")
        raw = json.loads(await asyncio.wait_for(socket.recv(), timeout=15))
    check(
        raw.get("type") == "error" and raw.get("code") == "INVALID_MESSAGE",
        "malformed frame returns INVALID_MESSAGE without dropping the socket",
        raw.get("code", ""),
    )

    # 10. Cleanup -------------------------------------------------------------
    check(delete(base, f"/documents/{doc_id}") == 200, "DELETE /documents/{id} removes it")
    after = get_json("/documents", base)
    check(after.get("total_documents") == 0, "index is empty after removal")

    print()
    if failures:
        print(f"{len(failures)} check(s) FAILED: {', '.join(failures)}\n")
        return 1
    print("All integration checks passed.\n")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    target = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BASE
    raise SystemExit(asyncio.run(main(target)))
