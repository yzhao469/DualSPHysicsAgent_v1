# mcp_server/tools

Tool implementations called by the MCP server.

## Files in this folder

| File | Main function / logic |
|---|---|
| `__init__.py` | Package marker for MCP tool implementations. |
| `_subprocess.py` | Shared async subprocess runner with timeout/error handling used by executable-wrapper tools. |
| `_xml_utils.py` | XML preprocessor that normalizes non-standard XML patterns before parsing/modification. |
| `generate_points.py` | Writes MeasureTool `POINTSLIST` files from explicit probe triples or x-z cross-product coordinates. |
| `metrics.py` | Computes RMSE/correlation-style comparison metrics between simulation CSV output and ground-truth CSV. |
| `run_gencase.py` | Invokes the GenCase binary to generate initial particle/case data from XML inputs. |
| `run_measuretool.py` | Invokes MeasureTool and collects generated probe CSV files from solver outputs. |
| `run_simulation.py` | Invokes DualSPHysics CPU/GPU solver binaries and returns execution results/paths. |
| `set_geometry.py` | Replaces and validates the `<geometry>` block in a case XML file before simulation build steps. |
| `xml_modifier.py` | Updates non-geometry XML parameters (constants, non-Newtonian phase values, execution settings). |
