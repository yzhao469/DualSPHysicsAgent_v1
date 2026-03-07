# dualsphysics-maf

LLM-assisted workflow for DualSPHysics non-Newtonian simulations.

## Quick start

1. Create a virtual environment and install the project:
   ```bash
   cd dualsphysics-maf
   python3.12 -m venv .venv
   .venv/bin/pip install -e .
   ```
2. Add your OpenAI API key to `dualsphysics-maf/.env`:
   ```bash
   echo "OPENAI_API_KEY=your_key_here" > .env
   ```
3. Run the interactive workflow:
   ```bash
   .venv/bin/python main.py
   ```

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

## Files in this folder

| File | Main function / logic |
|---|---|
| `.gitignore` | Ignores local runtime artifacts (`.venv`, `runs`, caches, logs, `.env`) from version control. |
| `CLAUDE.md` | Internal project notes describing the current workflow architecture and file responsibilities. |
| `README.md` | This index README for `dualsphysics-maf` folder-level documentation. |
| `datalake/` | Runtime working data folder used by the workflow to store/edit the active case XML (`Case_Def.xml`). |
| `main.py` | Main interactive workflow runner (planning → review → build → simulation) using event-driven HITL responses. |
| `main_smoke.py` | Alternate smoke entrypoint for explicit-parameter runs that bypass scenario-to-parameter reasoning. |
| `pyproject.toml` | Project metadata and pinned Python dependencies. |
| `requirements.txt` | Legacy dependency list (prefer `pip install -e .` via `pyproject.toml`). |
