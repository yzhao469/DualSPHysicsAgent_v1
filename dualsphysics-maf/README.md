# dualsphysics-maf

LLM-assisted workflow for DualSPHysics non-Newtonian simulations.

## Quick start

1. Create a virtual environment and install dependencies:
   ```bash
   cd dualsphysics-maf
   python3.12 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```
2. Update local absolute paths in:
   - `mcp_server/config.py` (`BASE_DIR`)
   - `agents/simulation_agent.py` (`BASE`)
3. Run the interactive workflow:
   ```bash
   .venv/bin/python main.py
   ```

## Folder READMEs

Each folder under `dualsphysics-maf` has its own README that documents every file in that folder and the file's main logic:

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
| `main.py` | Main interactive workflow runner (planning → review → build → simulation) using event-driven HITL responses. |
| `main_smoke.py` | Smoke test entrypoint that injects explicit parameters to validate the deterministic pipeline quickly. |
| `requirements.txt` | Python dependencies required by the agent framework, MCP server tooling, and metric/visualization utilities. |
