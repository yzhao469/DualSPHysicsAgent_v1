"""Agent 1 — SimulationRunner: drives a full DebrisFlow2D simulation end-to-end."""
from agent_framework import Agent, MCPStdioTool
from agent_framework.anthropic import AnthropicClient

BASE = "/home/danrong/projects/DualSPHysics_NN_v5.0.1/dualsphysics-maf"


def make_mcp_tool() -> MCPStdioTool:
    """Create the MCP stdio tool pointing at our DualSPHysics server."""
    return MCPStdioTool(
        name="dualsphysics",
        command=f"{BASE}/.venv/bin/python",
        args=[f"{BASE}/mcp_server/server.py"],
        cwd=BASE,
    )


def make_simulation_agent() -> Agent:
    """Create Agent 1 (SimulationRunner) with step-by-step instructions."""
    return Agent(
        client=AnthropicClient(model_id="claude-sonnet-4-6"),
        name="SimulationRunner",
        instructions=f"""You run DebrisFlow2D SPH simulations using DualSPHysics tools.

Given simulation parameters, follow these steps in order:

1. Choose a timestamped run directory:
   {BASE}/runs/run_<YYYYMMDD_HHMMSS>/
   Use the current UTC time to generate the timestamp.

2. Call modify_xml with:
   - base_xml = "{BASE}/cases/CaseDebrisFlow2D_Def.xml"
   - output_xml = <run_dir>/CaseDebrisFlow2D_Def.xml
   - plus any parameter values provided by the user.

3. Call run_gencase with:
   - xml_path = <run_dir>/CaseDebrisFlow2D_Def  (NO .xml extension)
   - output_dir = <run_dir>/out

4. Call run_simulation with:
   - case_path = <run_dir>/out/CaseDebrisFlow2D
   - output_dir = <run_dir>/out
   - gpu = False  (or True if the user explicitly requested GPU)

5. Call run_measuretool with:
   - data_dir = <run_dir>/out/data
   - points_file = "{BASE}/cases/CaseDebrisFlow2D_Points.txt"
   - output_csv_stem = <run_dir>/out/measuretool/PointsMeasure

6. Call compute_metrics with:
   - result_csv = <first CSV from run_measuretool csv_files list>
   - ground_truth_csv = "{BASE}/cases/ground_truth/PointsMeasure.csv"

7. Return a JSON summary:
   {{
     "params": <parameters used>,
     "rmse": <value or null>,
     "correlation": <value or null>,
     "run_dir": <run_dir>,
     "status": <"ok" or error description>
   }}

If any tool returns returncode != 0, report the stderr and stop.
If run_measuretool returns an empty csv_files list, report the error and stop.
""",
    )
