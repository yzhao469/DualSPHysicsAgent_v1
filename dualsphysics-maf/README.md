# dualsphysics-maf

LLM-assisted workflow for DualSPHysics non-Newtonian simulations.

## Quick start

1. Create a virtual environment and install the project:
   ```bash
   cd dualsphysics-maf
   python3.12 -m venv .venv
   .venv/bin/pip install -e .
   ```
2. Create your environment file from the template and add your OpenAI API key:
   ```bash
   cp .env.example .env
   # then edit .env and set OPENAI_API_KEY
   ```
   `.env.example` also pins the four per-role model variables to the settings
   used for the published results. If you set only `OPENAI_API_KEY` and skip
   the template, the code falls back to older default models and will **not**
   reproduce those runs — see the comments in `.env.example`.
3. Run the interactive workflow (choose **one**):

   **Terminal mode** (original CLI):
   ```bash
   .venv/bin/python main.py
   ```

   **Web GUI** (React + FastAPI):
   ```bash
   # Install frontend dependencies (first time only)
   cd gui-react && npm install && cd ..

   # Start the API server
   .venv/bin/uvicorn gui_api:app --host 0.0.0.0 --port 8000

   # In a separate terminal, start the React dev server
   cd gui-react && npm run dev
   ```
   Then open [http://localhost:5173](http://localhost:5173) in your browser.

   For a **production build** (single server):
   ```bash
   cd gui-react && npm run build && cd ..
   .venv/bin/uvicorn gui_api:app --host 0.0.0.0 --port 8000
   ```
   Open [http://localhost:8000](http://localhost:8000) — the FastAPI server
   serves the React static assets automatically.

   The GUI provides a chat interface, an XML editor, image viewer,
   shell-script editor, Python code viewer, and a file browser.

## Testing

Install the project with test dependencies and run the unit suite:

```bash
.venv/bin/pip install -e .[test]
.venv/bin/pytest
```

The initial pytest bootstrap focuses on fast unit coverage for pure helpers and
local file transformations under `agents/` and `mcp_server/tools/`. External
workflow paths that require MCP, OpenAI, or DualSPHysics binaries are left for
future mocked integration tests.

## Folder READMEs

Key folders under `dualsphysics-maf` have README files that document file responsibilities:

- [`agents/README.md`](agents/README.md)
- [`agents/prompts/README.md`](agents/prompts/README.md)
- [`agents/tools/README.md`](agents/tools/README.md)
- [`cases/README.md`](cases/README.md)
- [`cases/ground_truth/README.md`](cases/ground_truth/README.md)
- [`mcp_server/README.md`](mcp_server/README.md)
- [`mcp_server/tools/README.md`](mcp_server/tools/README.md)
- [`skills/README.md`](skills/README.md)
- [`tests/README.md`](tests/README.md)

## Files in this folder

| File | Main function / logic |
|---|---|
| `.gitignore` | Ignores local runtime artifacts (`.venv`, `runs`, caches, logs, `.env`) from version control. |
| `CLAUDE.md` | Internal project notes describing the current workflow architecture and file responsibilities. |
| `README.md` | This index README for `dualsphysics-maf` folder-level documentation. |
| `datalake/` | Runtime working data folder used by the workflow to store/edit the active case XML (`Case_Def.xml`). |
| `main.py` | Main interactive workflow runner (planning → review → build → simulation) using event-driven HITL responses. |
| `gui_api.py` | FastAPI backend — REST + WebSocket API for the React GUI, managing workflow state, file serving, and real-time event streaming. |
| `gui-react/` | React frontend — chat interface, XML/script editors, image viewer, Python code viewer, and file browser. |
| `main_smoke.py` | Alternate smoke entrypoint for explicit-parameter runs that bypass scenario-to-parameter reasoning. |
| `pyproject.toml` | Project metadata and pinned Python dependencies. |
| `requirements.txt` | Legacy dependency list (prefer `pip install -e .` via `pyproject.toml`). |
| `tests/` | Pytest-based test suite for unit coverage of schemas, XML helpers, file generation, skills loading, and metrics. |
