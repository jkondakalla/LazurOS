import json
import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from auth import CurrentUser

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("lazuros")

SHELL_URL        = os.getenv("SHELL_URL",        "http://localhost:3000")
COMPUTE_NODE_IP  = os.getenv("COMPUTE_NODE_IP",  "192.168.1.100")
COMPUTE_API_PORT = int(os.getenv("COMPUTE_API_PORT", "11434"))

app = FastAPI(title="LazurOS", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[SHELL_URL],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# ── Stub data ─────────────────────────────────────────────────────────────────

_STUB_MODELS = [
    {
        "name": "llama3.2:latest",
        "size": 2019393189,
        "digest": "stub",
        "modified_at": "2025-01-01T00:00:00Z",
    }
]

# BeigeBoard reads response.message.content, then JSON.parse()s it.
# Shape: { title, kind, scope, due_date, scheduled_time, notes }
_STUB_CHAT_CONTENT = json.dumps({
    "title": "Review meeting notes",
    "kind": "task",
    "scope": "day",
    "due_date": None,
    "scheduled_time": None,
    "notes": None,
})

# SylibOS reads response.response, then JSON.parse()s it.
# Shape: { quiz: [4 questions], tasks: [2 tasks] }
_STUB_GENERATE_RESPONSE = json.dumps({
    "quiz": [
        {
            "question": "What is the main concept introduced in this lecture?",
            "options": [
                "The primary concept",
                "A secondary concept",
                "An unrelated topic",
                "None of the above",
            ],
            "correctIndex": 0,
            "explanation": "The lecture primarily focuses on the core concept described in the title.",
        },
        {
            "question": "Which approach is most effective for understanding this material?",
            "options": [
                "Memorisation only",
                "Practical application",
                "Skipping prerequisites",
                "Passive reading",
            ],
            "correctIndex": 1,
            "explanation": "Practical application reinforces learning more effectively than passive study.",
        },
        {
            "question": "What is the recommended way to verify your understanding?",
            "options": [
                "Read the slides once",
                "Work through examples",
                "Watch videos only",
                "Ask someone else",
            ],
            "correctIndex": 1,
            "explanation": "Working through examples ensures active engagement with the material.",
        },
        {
            "question": "How does this topic relate to the broader course curriculum?",
            "options": [
                "It is completely isolated",
                "It builds on prior material",
                "It is optional context",
                "It contradicts earlier topics",
            ],
            "correctIndex": 1,
            "explanation": "Lecture topics build incrementally on previously established foundations.",
        },
    ],
    "tasks": [
        {
            "description": "Write a 3-sentence summary of the key ideas from this lecture in your own words.",
            "durationMinutes": 2,
        },
        {
            "description": "Identify one concept from this lecture you can apply today and write down how.",
            "durationMinutes": 2,
        },
    ],
})


# ── Public endpoints (no auth required) ──────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "lazuros": "ok",
        "compute_node": "up",
        "compute_online": True,
        "compute_ip": COMPUTE_NODE_IP,
        "compute_port": COMPUTE_API_PORT,
    }


# ── Authenticated management endpoints ───────────────────────────────────────

@app.post("/wake")
async def wake(_user: CurrentUser):
    return {"waking": False, "message": "Compute node is already online"}


@app.get("/models")
async def models(_user: CurrentUser):
    return {"sleeping": False, "models": _STUB_MODELS}


@app.get("/ps")
async def ps(_user: CurrentUser):
    return {"sleeping": False, "models": _STUB_MODELS}


# ── Authenticated proxy (catch-all — stub responses) ─────────────────────────

@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def proxy(request: Request, path: str, _user: CurrentUser):
    if request.method == "OPTIONS":
        return Response(status_code=204)

    # POST /api/chat — BeigeBoard task parse
    if path == "chat":
        log.info("[stub] /api/chat → returning hardcoded task fields")
        return {"message": {"content": _STUB_CHAT_CONTENT}, "done": True, "model": "llama3.2:stub"}

    # POST /api/generate — SylibOS nightly quiz/task generation
    if path == "generate":
        log.info("[stub] /api/generate → returning hardcoded quiz+tasks")
        return {"response": _STUB_GENERATE_RESPONSE, "done": True, "model": "llama3.2:stub"}

    # GET /api/tags — model list
    if path == "tags":
        return {"models": _STUB_MODELS}

    # GET /api/ps — loaded models
    if path == "ps":
        return {"models": _STUB_MODELS}

    log.warning("[stub] unhandled path: /api/%s", path)
    return Response(
        content='{"error": "stub: unhandled path"}',
        status_code=404,
        media_type="application/json",
    )
