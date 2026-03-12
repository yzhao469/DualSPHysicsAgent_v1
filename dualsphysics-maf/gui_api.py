"""DualSPHysics Simulation GUI — FastAPI backend.

Provides REST + WebSocket endpoints for the React frontend,
replacing the previous Streamlit-based GUI.

Run with:
    uvicorn gui_api:app --host 0.0.0.0 --port 8000 --reload
"""

import asyncio
import json
import logging
import os
import re
import threading
import uuid
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
load_dotenv(Path(__file__).resolve().parent / ".env")

from agent_framework import (          # noqa: E402
    AgentExecutor,
    WorkflowRunState,
)
from agents.schemas import (            # noqa: E402
    SetupReviewRequest,
    ResultsLoopRequest,
)
from agents.simulation_agent import (   # noqa: E402
    make_mcp_tool,
    make_simulation_agent,
)
from agents.workflow import build_workflow  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logging.getLogger("agent_framework").setLevel(logging.WARNING)
logging.getLogger("agent_framework._skills").setLevel(logging.INFO)
logger = logging.getLogger("dualsphysics_gui_api")

BASE = str(Path(__file__).resolve().parent)
RUNS_DIR = os.path.join(BASE, "runs")

# ═══════════════════════════════════════════════════════════════════════════════
# FastAPI app
# ═══════════════════════════════════════════════════════════════════════════════

app = FastAPI(title="DualSPHysics Simulation API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ═══════════════════════════════════════════════════════════════════════════════
# Session management
# ═══════════════════════════════════════════════════════════════════════════════


class Session:
    """Holds per-session workflow state."""

    def __init__(self) -> None:
        self.session_id: str = str(uuid.uuid4())
        self.messages: list[dict[str, str]] = []
        self.phase: str = "idle"  # idle | running | setup_review | results_loop | complete
        self.workflow_running: bool = False
        self.workflow_done: bool = False
        self.pending_request: dict | None = None
        self.run_dir: str | None = None
        self.selected_file: str | None = None
        self.event_queue: asyncio.Queue = asyncio.Queue()
        self.response_event: asyncio.Event = asyncio.Event()
        self.response_value: str | None = None
        self.shutdown_event: threading.Event = threading.Event()


# Single-session for simplicity (extend to dict for multi-user)
_session: Session | None = None


def _get_session() -> Session:
    global _session
    if _session is None:
        _session = Session()
    return _session


# ═══════════════════════════════════════════════════════════════════════════════
# Summary formatting (same as original gui.py)
# ═══════════════════════════════════════════════════════════════════════════════

_BANNER_RE = re.compile(r"^={3,}\s*$", re.MULTILINE)
_TERMINAL_PROMPTS = [
    "ParaView should be open with the particle configuration.",
    "Approve, request changes, or ask a question:",
    "Request changes to the post-processing script, run analysis,",
    "ask questions, or type 'done' to finish:",
]


def _clean_summary(text: str) -> str:
    """Convert terminal-style summary text to clean markdown."""
    text = _BANNER_RE.sub("", text)
    for prompt in _TERMINAL_PROMPTS:
        text = text.replace(prompt, "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(
        r"^\s*(SIMULATION (?:PLAN|RESULTS))\s*$",
        r"## \1",
        text,
        flags=re.MULTILINE,
    )
    return text.strip()


# ═══════════════════════════════════════════════════════════════════════════════
# File-system helpers (same as original gui.py)
# ═══════════════════════════════════════════════════════════════════════════════


def _find_latest_run_dir() -> str | None:
    if not os.path.isdir(RUNS_DIR):
        return None
    dirs = sorted(
        (d for d in Path(RUNS_DIR).iterdir() if d.is_dir() and d.name.startswith("run_")),
        key=lambda p: p.name,
        reverse=True,
    )
    return str(dirs[0]) if dirs else None


def _discover_files(run_dir: str | None) -> dict:
    """Return discovered files grouped by type."""
    if not run_dir or not os.path.isdir(run_dir):
        return {"key_files": {}, "images": [], "output_files": [], "python_scripts": []}

    rd = Path(run_dir)
    key_files: dict[str, str] = {}
    images: list[str] = []
    output_files: list[str] = []
    python_scripts: list[str] = []

    xml = rd / "Case_Def.xml"
    if xml.exists():
        key_files["xml"] = str(xml)

    sh = rd / "postprocess.sh"
    if sh.exists():
        key_files["script"] = str(sh)

    for p in sorted(rd.rglob("*.png")):
        images.append(str(p))

    analysis_dir = rd / "out" / "analysis"
    if analysis_dir.is_dir():
        for p in sorted(analysis_dir.glob("*.py")):
            python_scripts.append(str(p))

    seen: set[str] = set()
    for subdir in ("out/particles", "out/measuretool", "out/analysis", "out"):
        full = rd / subdir
        if full.is_dir():
            for f in sorted(full.iterdir()):
                if f.is_file() and str(f) not in seen:
                    output_files.append(str(f))
                    seen.add(str(f))

    return {
        "key_files": key_files,
        "images": images,
        "output_files": output_files,
        "python_scripts": python_scripts,
    }


def _file_icon(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    return {
        ".png": "🖼️", ".jpg": "🖼️", ".jpeg": "🖼️",
        ".csv": "📊", ".vtk": "📦", ".bi4": "📦",
        ".py": "🐍", ".xml": "📝", ".sh": "📜", ".txt": "📄",
    }.get(ext, "📄")


# ═══════════════════════════════════════════════════════════════════════════════
# Workflow ↔ API bridge (runs in a daemon thread)
# ═══════════════════════════════════════════════════════════════════════════════


async def _api_process_events(
    stream: Any,
    session: Session,
) -> dict | None:
    """Drain the workflow event stream, forwarding events to the session queue."""
    pending: dict[str, Any] = {}

    async for event in stream:
        if event.type == "request_info":
            data = event.data
            summary = (
                data.summary
                if isinstance(data, (SetupReviewRequest, ResultsLoopRequest))
                else str(data)
            )
            await session.event_queue.put({
                "type": "request_info",
                "summary": summary,
                "source": event.source_executor_id or "",
                "request_id": event.request_id,
            })
            # Wait for user response
            while True:
                if session.shutdown_event.is_set():
                    raise RuntimeError("Session ended while waiting for user reply")
                session.response_event.clear()
                try:
                    await asyncio.wait_for(session.response_event.wait(), timeout=5)
                except asyncio.TimeoutError:
                    continue
                break
            pending[event.request_id] = session.response_value

        elif event.type == "executor_failed":
            await session.event_queue.put({
                "type": "status",
                "message": f"⚠️ Executor `{event.executor_id}` failed: {event.details}",
            })

        elif event.type == "failed":
            await session.event_queue.put({
                "type": "status",
                "message": f"❌ Workflow failed: {event.details}",
            })

    result = await stream.get_final_response()
    state = result.get_final_state()

    if state == WorkflowRunState.IDLE_WITH_PENDING_REQUESTS:
        return pending

    outputs = result.get_outputs()
    if outputs:
        await session.event_queue.put({"type": "complete", "outputs": outputs})
    return None


async def _run_workflow(scenario: str, session: Session) -> None:
    mcp = make_mcp_tool()
    agent = make_simulation_agent()
    agent_exec = AgentExecutor(agent)
    wf = build_workflow(mcp=mcp, agent_executor=agent_exec, base_dir=BASE)

    await session.event_queue.put({
        "type": "status",
        "message": "🔄 Starting simulation workflow — this may take a moment…",
    })

    async with mcp:
        stream = wf.run(scenario, stream=True)
        responses = await _api_process_events(stream, session)
        while responses is not None:
            stream = wf.run(responses=responses, stream=True)
            responses = await _api_process_events(stream, session)

    await session.event_queue.put({"type": "done"})


def _workflow_thread(scenario: str, session: Session) -> None:
    """Thread entry-point."""
    try:
        asyncio.run(_run_workflow(scenario, session))
    except Exception as exc:
        logger.exception("Workflow thread error")
        loop = asyncio.new_event_loop()
        loop.run_until_complete(
            session.event_queue.put({"type": "status", "message": f"❌ Workflow error: {exc}"})
        )
        loop.run_until_complete(session.event_queue.put({"type": "done"}))
        loop.close()


# ═══════════════════════════════════════════════════════════════════════════════
# Event processing
# ═══════════════════════════════════════════════════════════════════════════════


def _apply_event(ev: dict, session: Session) -> None:
    t = ev["type"]

    if t == "request_info":
        session.pending_request = ev
        clean = _clean_summary(ev["summary"])
        session.messages.append({"role": "assistant", "content": clean})
        src = ev.get("source", "")
        if "setup_review" in src:
            session.phase = "setup_review"
        elif "results_loop" in src:
            session.phase = "results_loop"
        if not session.run_dir:
            session.run_dir = _find_latest_run_dir()

    elif t == "status":
        session.messages.append({"role": "assistant", "content": ev["message"]})

    elif t == "complete":
        body = "✅ **Simulation Complete!**\n\n"
        for out in ev.get("outputs", []):
            body += "```json\n" + json.dumps(out, indent=2, default=str) + "\n```\n"
        session.messages.append({"role": "assistant", "content": body})
        session.workflow_done = True
        session.phase = "complete"

    elif t == "done":
        session.workflow_running = False
        if not session.workflow_done:
            session.workflow_done = True


async def _drain_events(session: Session) -> list[dict]:
    """Drain all pending events and return them."""
    events = []
    while True:
        try:
            ev = session.event_queue.get_nowait()
            _apply_event(ev, session)
            events.append(ev)
        except asyncio.QueueEmpty:
            break
    return events


# ═══════════════════════════════════════════════════════════════════════════════
# Request / response models
# ═══════════════════════════════════════════════════════════════════════════════


class StartRequest(BaseModel):
    scenario: str


class RespondRequest(BaseModel):
    message: str


class SaveFileRequest(BaseModel):
    path: str
    content: str


# ═══════════════════════════════════════════════════════════════════════════════
# REST endpoints
# ═══════════════════════════════════════════════════════════════════════════════


@app.get("/api/state")
async def get_state():
    """Return current session state."""
    session = _get_session()
    await _drain_events(session)
    files = _discover_files(session.run_dir)
    return {
        "session_id": session.session_id,
        "messages": session.messages,
        "phase": session.phase,
        "workflow_running": session.workflow_running,
        "workflow_done": session.workflow_done,
        "pending_request": session.pending_request is not None,
        "run_dir": session.run_dir,
        "selected_file": session.selected_file,
        "files": files,
    }


@app.post("/api/workflow/start")
async def start_workflow(req: StartRequest):
    """Start the simulation workflow with a given scenario."""
    session = _get_session()
    if session.workflow_running:
        return JSONResponse(
            status_code=400,
            content={"error": "Workflow is already running"},
        )
    session.messages.append({"role": "user", "content": req.scenario})
    session.workflow_running = True
    session.phase = "running"

    t = threading.Thread(
        target=_workflow_thread,
        args=(req.scenario, session),
        daemon=True,
    )
    t.start()
    return {"status": "started"}


@app.post("/api/workflow/respond")
async def respond_to_workflow(req: RespondRequest):
    """Send a user response to the workflow (HITL)."""
    session = _get_session()
    session.messages.append({"role": "user", "content": req.message})

    if session.pending_request:
        session.response_value = req.message
        session.response_event.set()
        session.pending_request = None
        return {"status": "sent"}
    return {"status": "no_pending_request"}


@app.post("/api/workflow/reset")
async def reset_workflow():
    """Reset the session for a new workflow run."""
    global _session
    old = _session
    if old:
        old.shutdown_event.set()
    _session = Session()
    return {"status": "reset"}


@app.get("/api/files")
async def list_files():
    """List discovered files in the current run directory."""
    session = _get_session()
    return _discover_files(session.run_dir)


@app.get("/api/files/content")
async def get_file_content(path: str = Query(...)):
    """Get the text content of a file."""
    if not os.path.isfile(path):
        return JSONResponse(status_code=404, content={"error": "File not found"})
    # Security: only allow files under RUNS_DIR or BASE
    abs_path = os.path.abspath(path)
    if not (abs_path.startswith(os.path.abspath(RUNS_DIR)) or abs_path.startswith(os.path.abspath(BASE))):
        return JSONResponse(status_code=403, content={"error": "Access denied"})

    ext = os.path.splitext(path)[1].lower()
    if ext in (".png", ".jpg", ".jpeg"):
        return FileResponse(path, media_type=f"image/{ext.lstrip('.')}")
    if ext in (".vtk", ".bi4"):
        size = os.path.getsize(path)
        return {"type": "binary", "size": size, "name": os.path.basename(path)}

    try:
        content = Path(path).read_text(encoding="utf-8", errors="replace")
        lang = {".py": "python", ".xml": "xml", ".sh": "bash", ".bash": "bash", ".csv": "csv"}.get(ext, "text")
        return {"type": "text", "content": content, "language": lang, "name": os.path.basename(path)}
    except Exception:
        size = os.path.getsize(path)
        return {"type": "binary", "size": size, "name": os.path.basename(path)}


@app.get("/api/files/download")
async def download_file(path: str = Query(...)):
    """Download a file."""
    if not os.path.isfile(path):
        return JSONResponse(status_code=404, content={"error": "File not found"})
    abs_path = os.path.abspath(path)
    if not (abs_path.startswith(os.path.abspath(RUNS_DIR)) or abs_path.startswith(os.path.abspath(BASE))):
        return JSONResponse(status_code=403, content={"error": "Access denied"})
    return FileResponse(path, filename=os.path.basename(path))


@app.post("/api/files/save")
async def save_file(req: SaveFileRequest):
    """Save edited content to a file."""
    abs_path = os.path.abspath(req.path)
    if not (abs_path.startswith(os.path.abspath(RUNS_DIR)) or abs_path.startswith(os.path.abspath(BASE))):
        return JSONResponse(status_code=403, content={"error": "Access denied"})
    if not os.path.isfile(req.path):
        return JSONResponse(status_code=404, content={"error": "File not found"})

    Path(req.path).write_text(req.content)

    session = _get_session()
    name = os.path.basename(req.path)
    msg = f"I manually edited {name}. Please review my changes and proceed."
    session.messages.append({"role": "user", "content": msg})

    if session.pending_request:
        session.response_value = msg
        session.response_event.set()
        session.pending_request = None

    return {"status": "saved"}


@app.get("/api/files/image")
async def get_image(path: str = Query(...)):
    """Serve an image file."""
    if not os.path.isfile(path):
        return JSONResponse(status_code=404, content={"error": "File not found"})
    abs_path = os.path.abspath(path)
    if not (abs_path.startswith(os.path.abspath(RUNS_DIR)) or abs_path.startswith(os.path.abspath(BASE))):
        return JSONResponse(status_code=403, content={"error": "Access denied"})
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    media = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}.get(ext, "application/octet-stream")
    return FileResponse(path, media_type=media)


# ═══════════════════════════════════════════════════════════════════════════════
# WebSocket for real-time event streaming
# ═══════════════════════════════════════════════════════════════════════════════


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """Stream events to the frontend in real-time."""
    await ws.accept()
    session = _get_session()
    try:
        while True:
            # Drain events and send to frontend
            try:
                ev = await asyncio.wait_for(session.event_queue.get(), timeout=2)
                _apply_event(ev, session)
                await ws.send_json({
                    "event": ev,
                    "state": {
                        "phase": session.phase,
                        "workflow_running": session.workflow_running,
                        "workflow_done": session.workflow_done,
                        "pending_request": session.pending_request is not None,
                        "run_dir": session.run_dir,
                        "messages": session.messages,
                        "files": _discover_files(session.run_dir),
                    },
                })
            except asyncio.TimeoutError:
                # Send heartbeat to keep connection alive
                await ws.send_json({"event": {"type": "heartbeat"}})
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.exception("WebSocket error: %s", e)


# ═══════════════════════════════════════════════════════════════════════════════
# Serve static React build in production
# ═══════════════════════════════════════════════════════════════════════════════

_STATIC_DIR = os.path.join(os.path.dirname(__file__), "gui-react", "dist")
if os.path.isdir(_STATIC_DIR):
    from fastapi.staticfiles import StaticFiles

    # Serve assets from the React build
    app.mount("/assets", StaticFiles(directory=os.path.join(_STATIC_DIR, "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve the React SPA for any non-API route."""
        file_path = os.path.join(_STATIC_DIR, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(_STATIC_DIR, "index.html"))
