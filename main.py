import asyncio
import logging
import os
import socket
import time

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from wakeonlan import send_magic_packet

from auth import CurrentUser

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("lazuros")

COMPUTE_NODE_IP      = os.getenv("COMPUTE_NODE_IP", "192.168.1.100")
COMPUTE_NODE_MAC     = os.getenv("COMPUTE_NODE_MAC", "AA:BB:CC:DD:EE:FF")
COMPUTE_API_PORT     = int(os.getenv("COMPUTE_API_PORT", "11434"))
WAKE_TIMEOUT_SECONDS = int(os.getenv("WAKE_TIMEOUT_SECONDS", "45"))
SHELL_URL            = os.getenv("SHELL_URL", "http://localhost:3000")

COMPUTE_BASE_URL = f"http://{COMPUTE_NODE_IP}:{COMPUTE_API_PORT}"
CONNECT_TIMEOUT  = 1.0

app = FastAPI(title="LazurOS", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[SHELL_URL],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)


def _port_open(ip: str, port: int, timeout: float = CONNECT_TIMEOUT) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except OSError:
        return False


async def _wake_and_wait() -> bool:
    log.info("Compute node asleep — sending WoL to %s", COMPUTE_NODE_MAC)
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
    if _port_open(COMPUTE_NODE_IP, COMPUTE_API_PORT):
        return True
    return await _wake_and_wait()


# ── Public endpoints (no auth required) ──────────────────────────────────────

@app.get("/health")
async def health():
    alive = _port_open(COMPUTE_NODE_IP, COMPUTE_API_PORT)
    return {
        "lazuros": "ok",
        "compute_node": "up" if alive else "sleeping",
        "compute_online": alive,          # widget uses this field
        "compute_ip": COMPUTE_NODE_IP,
        "compute_port": COMPUTE_API_PORT,
    }


# ── Authenticated management endpoints ───────────────────────────────────────

@app.post("/wake")
async def wake(_user: CurrentUser):
    """Send a WoL packet to the compute node. Responds immediately; node may take up to WAKE_TIMEOUT_SECONDS to come up."""
    if _port_open(COMPUTE_NODE_IP, COMPUTE_API_PORT):
        return {"waking": False, "message": "Compute node is already online"}
    asyncio.create_task(_wake_and_wait())
    return {"waking": True, "message": f"WoL packet sent to {COMPUTE_NODE_MAC}"}


@app.get("/models")
async def models(_user: CurrentUser):
    """List available Ollama models. Returns sleeping=True and empty list if node is down."""
    if not _port_open(COMPUTE_NODE_IP, COMPUTE_API_PORT):
        return {"sleeping": True, "models": []}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{COMPUTE_BASE_URL}/api/tags")
            data = r.json()
            return {"sleeping": False, "models": data.get("models", [])}
    except Exception as e:
        log.error("Failed to fetch models: %s", e)
        return {"sleeping": False, "models": [], "error": str(e)}


@app.get("/ps")
async def ps(_user: CurrentUser):
    """Show currently running (loaded into VRAM) Ollama models."""
    if not _port_open(COMPUTE_NODE_IP, COMPUTE_API_PORT):
        return {"sleeping": True, "models": []}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{COMPUTE_BASE_URL}/api/ps")
            data = r.json()
            return {"sleeping": False, "models": data.get("models", [])}
    except Exception as e:
        log.error("Failed to fetch ps: %s", e)
        return {"sleeping": False, "models": [], "error": str(e)}


# ── Authenticated proxy (catch-all — forwards to Ollama) ─────────────────────

@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def proxy(request: Request, path: str, _user: CurrentUser):
    """Proxy all /api/* requests to Ollama on the compute node. Wakes node if sleeping."""
    if not await _ensure_compute_online():
        return Response(
            content='{"error": "Compute node did not wake in time"}',
            status_code=503,
            media_type="application/json",
        )

    target_url = f"{COMPUTE_BASE_URL}/api/{path}"
    if request.url.query:
        target_url = f"{target_url}?{request.url.query}"

    headers = dict(request.headers)
    for h in ("host", "content-length", "transfer-encoding", "connection", "cookie", "authorization"):
        headers.pop(h, None)

    body = await request.body()
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
