# DualSPHysics MAF

An LLM agent framework (MAF) for automating DualSPHysics non-Newtonian SPH simulations. An AI agent drives the full simulation pipeline — XML parameter injection, particle generation, simulation, probe measurement, and metrics — via a set of MCP tools.

## How It Works

```
main.py  →  Agent (Claude claude-sonnet-4-6)  →  MCP stdio  →  mcp_server/server.py
                                                                      ├─ modify_xml      (patch case XML)
                                                                      ├─ run_gencase     (generate particles)
                                                                      ├─ run_simulation  (DualSPHysics CPU/GPU)
                                                                      ├─ run_measuretool (probe CSVs)
                                                                      └─ compute_metrics (RMSE vs ground truth)
```

The agent receives simulation parameters, calls the 5 tools in sequence, and returns a JSON summary with RMSE and correlation against a ground-truth reference.

## Prerequisites

- **Python 3.12**
- **DualSPHysics v5.0 Non-Newtonian binaries** for Linux (64-bit), placed at:
  ```
  <repo-root>/../bin/linux/
  ├─ GenCase_linux64
  ├─ DualSPHysics5.0_NNewtonianCPU_linux64
  ├─ DualSPHysics5.0_NNewtonian_linux64   (GPU, optional)
  └─ MeasureTool_linux64
  ```
  The binaries also require stub Chrono shared libraries in the same directory:
  `libdsphchrono.so`, `libChronoEngine.so`, `libChronoEngine_parallel.so`

- **Anthropic API key** — set as the environment variable `ANTHROPIC_API_KEY`

## Setup

### 1. Clone and configure paths

> **Important:** Two files contain hardcoded absolute paths that you must update to match your machine.

**`mcp_server/config.py`** — update `BASE_DIR`:
```python
BASE_DIR = "/your/path/to/DualSPHysics_NN_v5.0.1"
```

**`agents/simulation_agent.py`** — update `BASE`:
```python
BASE = "/your/path/to/DualSPHysics_NN_v5.0.1/dualsphysics-maf"
```

### 2. Create a virtual environment and install dependencies

```bash
cd dualsphysics-maf
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### 3. Verify DualSPHysics binaries are executable

```bash
chmod +x ../bin/linux/GenCase_linux64
chmod +x ../bin/linux/DualSPHysics5.0_NNewtonianCPU_linux64
chmod +x ../bin/linux/MeasureTool_linux64
```

## Running Agent 1

```bash
ANTHROPIC_API_KEY=<your-key> .venv/bin/python main.py
```

The agent will:
1. Create a timestamped run directory under `runs/`
2. Patch `cases/CaseDebrisFlow2D_Def.xml` with the parameters in `main.py`
3. Run GenCase → DualSPHysics CPU solver → MeasureTool in sequence
4. Compare results against `cases/ground_truth/PointsMeasure.csv` (if it exists)
5. Print a JSON summary to stdout

### Generating ground truth

Run a full-length simulation (`TimeMax=5.0`) and copy the MeasureTool output:
```bash
cp runs/<run_dir>/out/measuretool/PointsMeasure_Rhop.csv \
   cases/ground_truth/PointsMeasure.csv
```

Once present, subsequent runs will compute RMSE and Pearson correlation against it.

## Project Structure

```
dualsphysics-maf/
├── main.py                          # Entry point — defines params and launches Agent 1
├── requirements.txt
├── agents/
│   └── simulation_agent.py          # Agent 1 definition (Claude + instructions)
├── mcp_server/
│   ├── server.py                    # FastMCP server exposing 5 tools over stdio
│   ├── config.py                    # Paths and timeouts — UPDATE PATHS FOR YOUR MACHINE
│   └── tools/
│       ├── xml_modifier.py          # Patches DualSPHysics case XML with new params
│       ├── run_gencase.py           # Runs GenCase binary
│       ├── run_simulation.py        # Runs DualSPHysics CPU/GPU solver
│       ├── run_measuretool.py       # Runs MeasureTool to extract probe CSVs
│       ├── metrics.py               # Computes RMSE and correlation vs ground truth
│       └── _subprocess.py           # Shared async subprocess helper
└── cases/
    ├── CaseDebrisFlow2D_Def.xml     # Base case definition (DebrisFlow2D)
    ├── CaseDebrisFlow2D_Points.txt  # Probe point definitions (6 points)
    └── ground_truth/
        └── PointsMeasure.csv        # Reference output (not committed — generate locally)
```

## Configurable Simulation Parameters

These can be passed to `modify_xml` (and therefore to the agent):

| Parameter | Description |
|---|---|
| `dp` | Initial particle spacing (m) |
| `coefh` | Smoothing length coefficient |
| `cflnumber` | CFL number for time-step control |
| `Visco` | Viscosity model selector |
| `DensityDT` | Density diffusion type |
| `DensityDTvalue` | Density diffusion coefficient |
| `TimeMax` | Simulation end time (s) |
| `TimeOut` | Output interval (s) |
| `visco_nn` | Non-Newtonian viscosity |
| `tau_yield` | Yield stress (Herschel-Bulkley) |
| `HBP_m` | Herschel-Bulkley consistency index |
| `HBP_n` | Herschel-Bulkley flow index |
