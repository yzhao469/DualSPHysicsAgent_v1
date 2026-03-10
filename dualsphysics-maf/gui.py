"""DualSPHysics Simulation GUI — Streamlit web interface.

Provides a rich chat + multi-panel UI for every workflow phase:
  • Pre-simulation  — XML editor (editable) + geometry image viewer
  • Post-simulation — shell-script editor (editable) + Python code viewer
                      + clickable file / image browser

Run with:
    streamlit run gui.py
"""

import asyncio
import json
import logging
import os
import queue
import threading
from pathlib import Path
from typing import Any

import streamlit as st
from dotenv import load_dotenv

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
logger = logging.getLogger("dualsphysics_gui")

BASE = str(Path(__file__).resolve().parent)
RUNS_DIR = os.path.join(BASE, "runs")

# ═══════════════════════════════════════════════════════════════════════════════
# Page configuration  (deferred until main() so the module is safely importable)
# ═══════════════════════════════════════════════════════════════════════════════

_CSS = """
<style>
.stTabs [data-baseweb="tab-list"] { gap: 8px; }
.stTabs [data-baseweb="tab"]      { padding: 8px 16px; border-radius: 4px; }
</style>
"""

# ═══════════════════════════════════════════════════════════════════════════════
# Session-state defaults
# ═══════════════════════════════════════════════════════════════════════════════
_DEFAULTS: dict[str, Any] = {
    "messages": [],
    "workflow_running": False,
    "workflow_done": False,
    "event_queue": queue.Queue(),
    "response_queue": queue.Queue(),
    "pending_request": None,
    "run_dir": None,
    "phase": "idle",          # idle | running | setup_review | results_loop | complete
    "selected_file": None,
}


def _init_session_state() -> None:
    for k, v in _DEFAULTS.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ═══════════════════════════════════════════════════════════════════════════════
# Workflow ↔ GUI bridge  (runs in a daemon thread)
# ═══════════════════════════════════════════════════════════════════════════════

async def _gui_process_events(stream: Any, eq: queue.Queue, rq: queue.Queue) -> dict | None:
    """Drain the workflow event stream, forwarding events over *eq*.

    Blocks on *rq* whenever the workflow asks for user input.
    """
    pending: dict[str, Any] = {}

    async for event in stream:
        if event.type == "request_info":
            data = event.data
            summary = data.summary if isinstance(data, (SetupReviewRequest, ResultsLoopRequest)) else str(data)
            eq.put({
                "type": "request_info",
                "summary": summary,
                "source": event.source_executor_id or "",
                "request_id": event.request_id,
            })
            response = rq.get()               # block until the user replies
            pending[event.request_id] = response

        elif event.type == "executor_failed":
            eq.put({"type": "status", "message": f"⚠️ Executor `{event.executor_id}` failed: {event.details}"})

        elif event.type == "failed":
            eq.put({"type": "status", "message": f"❌ Workflow failed: {event.details}"})

    result = await stream.get_final_response()
    state = result.get_final_state()

    if state == WorkflowRunState.IDLE_WITH_PENDING_REQUESTS:
        return pending

    outputs = result.get_outputs()
    if outputs:
        eq.put({"type": "complete", "outputs": outputs})
    return None


async def _run_workflow(scenario: str, eq: queue.Queue, rq: queue.Queue) -> None:
    mcp = make_mcp_tool()
    agent = make_simulation_agent()
    agent_exec = AgentExecutor(agent)
    wf = build_workflow(mcp=mcp, agent_executor=agent_exec, base_dir=BASE)

    eq.put({"type": "status", "message": "🔄 Starting simulation workflow — this may take a moment…"})

    async with mcp:
        stream = wf.run(scenario, stream=True)
        responses = await _gui_process_events(stream, eq, rq)
        while responses is not None:
            stream = wf.run(responses=responses, stream=True)
            responses = await _gui_process_events(stream, eq, rq)

    eq.put({"type": "done"})


def _workflow_thread(scenario: str, eq: queue.Queue, rq: queue.Queue) -> None:
    """Thread entry-point."""
    try:
        asyncio.run(_run_workflow(scenario, eq, rq))
    except Exception as exc:
        logger.exception("Workflow thread error")
        eq.put({"type": "status", "message": f"❌ Workflow error: {exc}"})
        eq.put({"type": "done"})


# ═══════════════════════════════════════════════════════════════════════════════
# File-system helpers
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


def _discover_files(run_dir: str | None):
    """Return (key_files, images, output_files, python_scripts)."""
    if not run_dir or not os.path.isdir(run_dir):
        return {}, [], [], []

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

    return key_files, images, output_files, python_scripts


def _file_icon(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    return {
        ".png": "🖼️", ".jpg": "🖼️", ".jpeg": "🖼️",
        ".csv": "📊", ".vtk": "📦", ".bi4": "📦",
        ".py": "🐍", ".xml": "📝", ".sh": "📜", ".txt": "📄",
    }.get(ext, "📄")


# ═══════════════════════════════════════════════════════════════════════════════
# Event processing
# ═══════════════════════════════════════════════════════════════════════════════

def _drain_event_queue() -> bool:
    """Process every pending event.  Return *True* when at least one was found."""
    eq: queue.Queue = st.session_state.event_queue
    changed = False
    while True:
        try:
            ev = eq.get_nowait()
        except queue.Empty:
            break
        changed = True
        _apply_event(ev)
    return changed


def _apply_event(ev: dict) -> None:
    t = ev["type"]

    if t == "request_info":
        st.session_state.pending_request = ev
        st.session_state.messages.append({"role": "assistant", "content": ev["summary"]})
        src = ev.get("source", "")
        if "setup_review" in src:
            st.session_state.phase = "setup_review"
        elif "results_loop" in src:
            st.session_state.phase = "results_loop"
        if not st.session_state.run_dir:
            st.session_state.run_dir = _find_latest_run_dir()

    elif t == "status":
        st.session_state.messages.append({"role": "assistant", "content": ev["message"]})

    elif t == "complete":
        body = "✅ **Simulation Complete!**\n\n"
        for out in ev.get("outputs", []):
            body += "```json\n" + json.dumps(out, indent=2, default=str) + "\n```\n"
        st.session_state.messages.append({"role": "assistant", "content": body})
        st.session_state.workflow_done = True
        st.session_state.phase = "complete"

    elif t == "done":
        st.session_state.workflow_running = False
        if not st.session_state.workflow_done:
            st.session_state.workflow_done = True


# ═══════════════════════════════════════════════════════════════════════════════
# Polling fragment  (auto-refreshes when events arrive)
# ═══════════════════════════════════════════════════════════════════════════════

@st.fragment(run_every=2)
def _event_poller():
    if not st.session_state.get("workflow_running"):
        return
    if _drain_event_queue():
        st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# UI — sidebar
# ═══════════════════════════════════════════════════════════════════════════════

def _render_sidebar(key_files, images, output_files, python_scripts, run_dir):
    with st.sidebar:
        st.header("🌊 DualSPHysics")

        phase_labels = {
            "idle": "⚪ Ready",
            "running": "🔄 Processing…",
            "setup_review": "🔍 Setup Review",
            "results_loop": "📊 Post-Processing",
            "complete": "✅ Complete",
        }
        st.info(phase_labels.get(st.session_state.phase, st.session_state.phase))

        if st.session_state.workflow_running and not st.session_state.pending_request:
            st.caption("⏳ Agent is working…")

        # New-session button
        if st.session_state.workflow_done:
            if st.button("🔄 New Session"):
                for k, v in _DEFAULTS.items():
                    st.session_state[k] = v
                st.rerun()

        st.divider()

        # Key files
        if key_files:
            st.subheader("📌 Key Files")
            if "xml" in key_files:
                st.caption(f"XML: `Case_Def.xml`")
            if "script" in key_files:
                st.caption(f"Script: `postprocess.sh`")

        # Generated files grouped by type
        if images or output_files or python_scripts:
            st.subheader("📁 Generated Files")

            if images:
                with st.expander(f"🖼️ Images ({len(images)})"):
                    for img in images:
                        if st.button(
                            f"🖼️ {os.path.basename(img)}",
                            key=f"sb_img_{img}",
                            use_container_width=True,
                        ):
                            st.session_state.selected_file = img

            if python_scripts:
                with st.expander(f"🐍 Python ({len(python_scripts)})"):
                    for s in python_scripts:
                        if st.button(
                            f"🐍 {os.path.basename(s)}",
                            key=f"sb_py_{s}",
                            use_container_width=True,
                        ):
                            st.session_state.selected_file = s

            if output_files:
                with st.expander(f"📄 All Files ({len(output_files)})"):
                    for fp in output_files[:60]:
                        name = os.path.relpath(fp, run_dir) if run_dir else os.path.basename(fp)
                        if st.button(
                            f"{_file_icon(fp)} {name}",
                            key=f"sb_f_{fp}",
                            use_container_width=True,
                        ):
                            st.session_state.selected_file = fp


# ═══════════════════════════════════════════════════════════════════════════════
# UI — main panels
# ═══════════════════════════════════════════════════════════════════════════════

def _render_chat():
    """Scrollable chat message container."""
    container = st.container(height=550)
    with container:
        if not st.session_state.messages:
            st.markdown(
                "👋 **Welcome to DualSPHysics Simulation!**\n\n"
                "Describe your simulation scenario below to get started.\n\n"
                "_Example: Simulate a moderately dense debris flow with shear-thinning "
                "non-Newtonian material, 0.8 m wide and 1.0 m tall fluid column in a 4 m "
                "channel, density 1500 kg/m³, run for 2 s._"
            )
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])


def _render_xml_editor(xml_path: str | None):
    """XML file viewer / editor with syntax highlighting and save."""
    if not xml_path or not os.path.exists(xml_path):
        st.info("📝 No XML file available yet. Start a simulation to generate one.")
        return

    content = Path(xml_path).read_text()

    c1, _, c3 = st.columns([1, 2, 1])
    with c1:
        edit_mode = st.toggle("✏️ Edit", key="xml_edit_toggle")
    with c3:
        st.download_button("⬇️ Download", data=content, file_name="Case_Def.xml", mime="application/xml")

    if edit_mode:
        edited = st.text_area(
            "Edit XML",
            value=content,
            height=500,
            key="xml_editor_area",
            label_visibility="collapsed",
        )
        if st.button("💾 Save Changes", key="save_xml", type="primary"):
            Path(xml_path).write_text(edited)
            st.success("✅ XML file saved!")
            st.rerun()
    else:
        st.code(content, language="xml", line_numbers=True)


def _render_visualization(images: list[str]):
    """Geometry / results image viewer."""
    if not images:
        st.info("🖼️ No visualizations available yet.")
        return

    if len(images) > 1:
        selected = st.selectbox(
            "Select image",
            images,
            format_func=lambda x: os.path.basename(x),
        )
    else:
        selected = images[0]

    if selected and os.path.exists(selected):
        st.image(selected, caption=os.path.basename(selected), use_container_width=True)


def _render_script_editor(script_path: str | None):
    """Shell script viewer / editor."""
    if not script_path or not os.path.exists(script_path):
        st.info("📜 No post-processing script available yet.")
        return

    content = Path(script_path).read_text()

    c1, _, c3 = st.columns([1, 2, 1])
    with c1:
        edit_mode = st.toggle("✏️ Edit", key="script_edit_toggle")
    with c3:
        st.download_button("⬇️ Download", data=content, file_name="postprocess.sh", mime="text/x-shellscript")

    if edit_mode:
        edited = st.text_area(
            "Edit Script",
            value=content,
            height=400,
            key="script_editor_area",
            label_visibility="collapsed",
        )
        if st.button("💾 Save Changes", key="save_script", type="primary"):
            Path(script_path).write_text(edited)
            st.success("✅ Script saved!")
            st.rerun()
    else:
        st.code(content, language="bash", line_numbers=True)


def _render_python_code(python_scripts: list[str]):
    """Python code generated by the agent."""
    if not python_scripts:
        st.info(
            "🐍 No Python scripts generated yet. "
            "The agent creates analysis scripts during post-processing."
        )
        return

    for sp in python_scripts:
        if os.path.exists(sp):
            name = os.path.basename(sp)
            with st.expander(f"🐍 {name}", expanded=len(python_scripts) == 1):
                st.code(Path(sp).read_text(), language="python", line_numbers=True)
                st.download_button(
                    f"⬇️ Download {name}",
                    data=Path(sp).read_text(),
                    file_name=name,
                    mime="text/x-python",
                    key=f"dl_py_{sp}",
                )


def _render_file_browser(output_files: list[str], run_dir: str | None):
    """Clickable file browser with inline previews."""
    if not output_files:
        st.info("📁 No output files generated yet.")
        return

    # Group by sub-directory
    grouped: dict[str, list[str]] = {}
    for fp in output_files:
        rel = os.path.relpath(fp, run_dir) if run_dir else fp
        d = os.path.dirname(rel) or "root"
        grouped.setdefault(d, []).append(fp)

    for d, files in sorted(grouped.items()):
        with st.expander(f"📂 {d} ({len(files)} files)", expanded=True):
            for fp in files:
                name = os.path.basename(fp)
                if st.button(
                    f"{_file_icon(fp)} {name}",
                    key=f"fb_{fp}",
                    use_container_width=True,
                ):
                    st.session_state.selected_file = fp

    # Preview selected file
    sel = st.session_state.get("selected_file")
    if sel and os.path.exists(sel):
        st.divider()
        st.subheader(f"Viewing: {os.path.basename(sel)}")
        _file_preview(sel)


def _file_preview(path: str):
    """Render an inline preview for the given file."""
    ext = os.path.splitext(path)[1].lower()

    if ext in (".png", ".jpg", ".jpeg"):
        st.image(path, use_container_width=True)
    elif ext == ".csv":
        try:
            import pandas as pd
            df = pd.read_csv(path, sep=None, engine="python", nrows=200)
            st.dataframe(df, use_container_width=True)
        except Exception as e:
            st.error(f"Could not parse CSV: {e}")
    elif ext == ".py":
        st.code(Path(path).read_text(), language="python", line_numbers=True)
    elif ext == ".xml":
        st.code(Path(path).read_text(), language="xml", line_numbers=True)
    elif ext in (".sh", ".bash"):
        st.code(Path(path).read_text(), language="bash", line_numbers=True)
    elif ext in (".txt", ".log"):
        st.code(Path(path).read_text(), line_numbers=True)
    elif ext in (".vtk", ".bi4"):
        st.info(f"Binary file — {os.path.getsize(path):,} bytes")
    else:
        try:
            st.code(Path(path).read_text(), line_numbers=True)
        except Exception:
            st.info(f"Binary file — {os.path.getsize(path):,} bytes")


# ═══════════════════════════════════════════════════════════════════════════════
# Main layout
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    st.set_page_config(
        page_title="DualSPHysics Simulation",
        page_icon="🌊",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(_CSS, unsafe_allow_html=True)
    _init_session_state()

    # 1. Drain any queued events
    _drain_event_queue()

    # 2. Discover files
    run_dir = st.session_state.run_dir or _find_latest_run_dir()
    key_files, images, output_files, python_scripts = _discover_files(run_dir)

    # 3. Sidebar
    _render_sidebar(key_files, images, output_files, python_scripts, run_dir)

    # 4. Title
    st.title("🌊 DualSPHysics Simulation")

    # 5. Tabbed panels (vary by workflow phase)
    phase = st.session_state.phase

    if phase == "setup_review":
        tabs = st.tabs(["💬 Chat", "📝 XML Editor", "🖼️ Visualization"])
        with tabs[0]:
            _render_chat()
        with tabs[1]:
            _render_xml_editor(key_files.get("xml"))
        with tabs[2]:
            _render_visualization(images)

    elif phase in ("results_loop", "complete"):
        tabs = st.tabs([
            "💬 Chat",
            "📜 Shell Script",
            "🐍 Python Code",
            "🖼️ Visualization",
            "📁 Files",
        ])
        with tabs[0]:
            _render_chat()
        with tabs[1]:
            _render_script_editor(key_files.get("script"))
        with tabs[2]:
            _render_python_code(python_scripts)
        with tabs[3]:
            _render_visualization(images)
        with tabs[4]:
            _render_file_browser(output_files, run_dir)

    else:
        _render_chat()

    # 6. Background event poller
    _event_poller()

    # 7. Chat input (always pinned at the bottom)
    placeholder = (
        "Describe your simulation scenario…"
        if phase == "idle"
        else "Type your response…"
    )

    if user_input := st.chat_input(placeholder):
        st.session_state.messages.append({"role": "user", "content": user_input})

        if not st.session_state.workflow_running and not st.session_state.workflow_done:
            # Launch the workflow in a background thread
            st.session_state.workflow_running = True
            st.session_state.phase = "running"
            t = threading.Thread(
                target=_workflow_thread,
                args=(
                    user_input,
                    st.session_state.event_queue,
                    st.session_state.response_queue,
                ),
                daemon=True,
            )
            t.start()

        elif st.session_state.pending_request:
            # Forward the reply to the blocked workflow thread
            st.session_state.response_queue.put(user_input)
            st.session_state.pending_request = None

        st.rerun()


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    main()
