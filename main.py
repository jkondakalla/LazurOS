import asyncio
import logging
import os
import socket
import time

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse
from wakeonlan import send_magic_packet

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("lazuros")

COMPUTE_NODE_IP = os.getenv("COMPUTE_NODE_IP", "192.168.1.100")
COMPUTE_NODE_MAC = os.getenv("COMPUTE_NODE_MAC", "AA:BB:CC:DD:EE:FF")
COMPUTE_API_PORT = int(os.getenv("COMPUTE_API_PORT", "11434"))
WAKE_TIMEOUT_SECONDS = int(os.getenv("WAKE_TIMEOUT_SECONDS", "45"))

COMPUTE_BASE_URL = f"http://{COMPUTE_NODE_IP}:{COMPUTE_API_PORT}"
CONNECT_TIMEOUT = 1.0  # seconds for health probe

app = FastAPI(title="LazurOS", version="0.1.0")


def _port_open(ip: str, port: int, timeout: float = CONNECT_TIMEOUT) -> bool:
    """Quick TCP probe — returns True if the port accepts connections."""
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except OSError:
        return False


async def _wake_and_wait() -> bool:
    """Send WoL packet, then poll until compute API port is open or timeout."""
    log.info("Compute node is asleep — sending Wake-on-LAN to %s", COMPUTE_NODE_MAC)
    send_magic_packet(COMPUTE_NODE_MAC)

    deadline = time.monotonic() + WAKE_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if _port_open(COMPUTE_NODE_IP, COMPUTE_API_PORT):
            log.info("Compute node is up.")
            return True
        await asyncio.sleep(1)

    log.error("Compute node did not respond within %ds.", WAKE_TIMEOUT_SECONDS)
    return False


async def _ensure_compute_online() -> bool:
    """Fast path if awake, wake path if not."""
    if _port_open(COMPUTE_NODE_IP, COMPUTE_API_PORT):
        return True
    return await _wake_and_wait()


@app.get("/health")
async def health():
    alive = _port_open(COMPUTE_NODE_IP, COMPUTE_API_PORT)
    return {"lazuros": "ok", "compute_node": "up" if alive else "sleeping"}


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def proxy(request: Request, path: str):
    if not await _ensure_compute_online():
        return Response(
            content='{"error": "Compute node did not wake in time"}',
            status_code=503,
            media_type="application/json",
        )

    target_url = f"{COMPUTE_BASE_URL}/{path}"
    if request.url.query:
        target_url = f"{target_url}?{request.url.query}"

    headers = dict(request.headers)
    # Strip hop-by-hop headers that must not be forwarded
    for h in ("host", "content-length", "transfer-encoding", "connection"):
        headers.pop(h, None)

    body = await request.body()

    # Detect streaming intent: OpenAI clients set stream=true in JSON body
    wants_stream = b'"stream":true' in body or b'"stream": true' in body

    async with httpx.AsyncClient(timeout=None) as client:
        if wants_stream:
            async def _stream_gen():
                async with client.stream(
                    request.method,
                    target_url,
                    headers=headers,
                    content=body,
                ) as upstream:
                    async for chunk in upstream.aiter_raw():
                        yield chunk

            return StreamingResponse(
                _stream_gen(),
                media_type="text/event-stream",
                headers={"X-Accel-Buffering": "no"},
            )
        else:
            upstream = await client.request(
                request.method,
                target_url,
                headers=headers,
                content=body,
            )
            return Response(
                content=upstream.content,
                status_code=upstream.status_code,
                headers=dict(upstream.headers),
            )
