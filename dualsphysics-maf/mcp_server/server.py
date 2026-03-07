"""DualSPHysics MCP Server — 7 tools for SPH simulation control."""
import logging
import os
import sys

# Ensure the mcp_server package is importable when run as __main__
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp.server.fastmcp import FastMCP

from tools.xml_modifier import modify_xml as _modify_xml
from tools.set_geometry import set_geometry as _set_geometry
from tools.generate_points import generate_points_file as _generate_points_file
from tools.run_gencase import run_gencase as _run_gencase
from tools.run_simulation import run_simulation as _run_simulation
from tools.run_measuretool import run_measuretool as _run_measuretool
from tools.metrics import compute_metrics as _compute_metrics
from tools.postprocess import run_postprocess as _run_postprocess
from tools.run_analysis import run_analysis as _run_analysis

# ---------------------------------------------------------------------------
# Logging: file + stderr (stderr goes to MCP client; file persists)
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "mcp_server.log")
        ),
        logging.StreamHandler(sys.stderr),
    ],
)
logger = logging.getLogger("dualsphysics_mcp")

# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------
mcp = FastMCP("dualsphysics")


@mcp.tool()
def set_geometry(
    base_xml: str,
    output_xml: str,
    geometry_xml: str,
) -> str:
    """Replace the <geometry> block in the case XML with a new one.

    The agent generates the full <geometry> XML (including <definition>,
    <commands><mainlist>, drawing commands, etc.) and this tool validates
    and splices it into the case file.

    Validation checks:
    - Root tag is <geometry>
    - Contains <definition dp="..."> with positive numeric dp
    - Contains <commands><mainlist> with at least one child
    - Contains <pointmin> and <pointmax>

    Args:
        base_xml:     Path to the source case XML file.
        output_xml:   Path to write the modified XML.
        geometry_xml: The full <geometry>...</geometry> XML string.

    Returns a descriptive success or error string.
    """
    logger.info("set_geometry: base=%s output=%s geom_len=%d",
                base_xml, output_xml, len(geometry_xml))
    result = _set_geometry(base_xml, output_xml, geometry_xml)
    logger.info("set_geometry: %s", result)
    return result


@mcp.tool()
def modify_xml(
    base_xml: str,
    output_xml: str,
    # constantsdef
    gravity_z: float | None = None,
    rhop0: float | None = None,
    coefh: float | None = None,
    cflnumber: float | None = None,
    # non-Newtonian phase (mkfluid=0)
    phase_rhop: float | None = None,
    visco_nn: float | None = None,
    tau_yield: float | None = None,
    HBP_m: float | None = None,
    HBP_n: float | None = None,
    # execution/parameters
    Visco: float | None = None,
    DensityDT: int | None = None,
    DensityDTvalue: float | None = None,
    TimeMax: float | None = None,
    TimeOut: float | None = None,
) -> str:
    """Modify physics and execution parameters in a case XML.

    Use set_geometry for geometry changes (dp, drawing commands, domain bounds).
    Only parameters that are explicitly provided (non-None) are modified.

    constantsdef:
      gravity_z  - gravitational acceleration z-component (default -9.81 m/s²)
      rhop0      - reference density (kg/m³); should match phase_rhop
      coefh      - smoothing length coefficient
      cflnumber  - CFL timestep multiplier

    Non-Newtonian phase (mkfluid=0):
      phase_rhop - phase density (kg/m³)
      visco_nn   - consistency index (m²/s)
      tau_yield  - specific yield stress (Pa·m³/kg)
      HBP_m      - regularisation parameter (s)
      HBP_n      - flow index (<1 shear-thinning, >1 shear-thickening)

    Returns the path to the output XML file.
    """
    changed = {k: v for k, v in locals().items()
               if v is not None and k not in ("base_xml", "output_xml")}
    logger.info("modify_xml: base=%s output=%s params=%s", base_xml, output_xml, changed)

    result = _modify_xml(
        base_xml=base_xml,
        output_xml=output_xml,
        gravity_z=gravity_z,
        rhop0=rhop0,
        coefh=coefh,
        cflnumber=cflnumber,
        phase_rhop=phase_rhop,
        visco_nn=visco_nn,
        tau_yield=tau_yield,
        HBP_m=HBP_m,
        HBP_n=HBP_n,
        Visco=Visco,
        DensityDT=DensityDT,
        DensityDTvalue=DensityDTvalue,
        TimeMax=TimeMax,
        TimeOut=TimeOut,
    )
    logger.info("modify_xml: done -> %s", result)
    return result


@mcp.tool()
def generate_points_file(
    output_path: str,
    probe_xs: list | None = None,
    probe_zs: list | None = None,
    y: float = 1.0,
    probe_points: list | None = None,
) -> str:
    """Write a MeasureTool POINTSLIST file for the given probe coordinates.

    Two modes:
    1. Explicit triples (preferred for general geometry):
       Pass probe_points as a list of [x, y, z] triples.
    2. Cross-product (legacy, for 2D channel cases):
       Pass probe_xs and probe_zs; one block per (x, z) at fixed y.

    If both are provided, probe_points takes precedence.

    Args:
        output_path:  Path to write the points file.
        probe_xs:     List of x coordinates (m) — cross-product mode.
        probe_zs:     List of z coordinates (m) — cross-product mode.
        y:            Fixed y coordinate (m); default 1.0.
        probe_points: List of [x, y, z] triples — explicit mode.

    Returns:
        The path to the written file.
    """
    n = len(probe_points) if probe_points else (
        len(probe_xs or []) * len(probe_zs or []))
    logger.info("generate_points_file: output=%s n_probes=%d", output_path, n)
    result = _generate_points_file(
        output_path, probe_xs=probe_xs, probe_zs=probe_zs, y=y,
        probe_points=probe_points,
    )
    logger.info("generate_points_file: wrote %d probes to %s", n, result)
    return result


@mcp.tool()
async def run_gencase(xml_path: str, output_dir: str) -> dict:
    """Run GenCase to generate particle configuration from XML.

    Args:
        xml_path:   Path to the case XML WITHOUT the .xml extension.
        output_dir: Directory where GenCase will write output files.

    Returns dict with returncode, stdout, stderr, output_dir.
    """
    logger.info("run_gencase: xml_path=%s output_dir=%s", xml_path, output_dir)
    result = await _run_gencase(xml_path, output_dir)
    logger.info("run_gencase: returncode=%d", result["returncode"])
    return result


@mcp.tool()
async def run_simulation(case_path: str, output_dir: str, gpu: bool = False) -> dict:
    """Run DualSPHysics non-Newtonian solver (CPU or GPU).

    Args:
        case_path:  Path to the GenCase output case (e.g. out/CaseDebrisFlow2D),
                    without file extension.
        output_dir: Directory where the solver writes its output.
        gpu:        Set True to use the GPU binary; default False uses CPU.

    Returns dict with returncode, stdout, stderr, data_dir, gpu.
    """
    logger.info("run_simulation: case_path=%s output_dir=%s gpu=%s",
                case_path, output_dir, gpu)
    result = await _run_simulation(case_path, output_dir, gpu=gpu)
    logger.info("run_simulation: returncode=%d data_dir=%s",
                result["returncode"], result.get("data_dir"))
    return result


@mcp.tool()
async def run_measuretool(data_dir: str, points_file: str, output_csv_stem: str) -> dict:
    """Run MeasureTool to extract velocity and density at probe points.

    Args:
        data_dir:         Directory containing the simulation .bi4 part files.
        points_file:      Path to the POINTSLIST file defining probe locations.
        output_csv_stem:  Stem path for -savecsv (MeasureTool appends suffixes).

    Returns dict with returncode, stdout, stderr, csv_files (list of found CSVs).
    """
    logger.info("run_measuretool: data_dir=%s points_file=%s stem=%s",
                data_dir, points_file, output_csv_stem)
    result = await _run_measuretool(data_dir, points_file, output_csv_stem)
    logger.info("run_measuretool: returncode=%d csv_files=%s",
                result["returncode"], result.get("csv_files"))
    return result


@mcp.tool()
def compute_metrics(result_csv: str, ground_truth_csv: str) -> dict:
    """Compute RMSE and correlation between simulation output and ground truth.

    Args:
        result_csv:       Path to the MeasureTool output CSV.
        ground_truth_csv: Path to the reference/ground-truth CSV.

    Returns dict with status, rmse, correlation, max_error, num_timesteps, num_probes.
    If ground_truth_csv does not exist, returns {"status": "no_ground_truth"}.
    """
    logger.info("compute_metrics: result=%s gt=%s", result_csv, ground_truth_csv)
    result = _compute_metrics(result_csv, ground_truth_csv)
    logger.info("compute_metrics: %s", result)
    return result


@mcp.tool()
async def run_postprocess(postprocess_tool: str, args: list[str], cwd: str | None = None) -> dict:
    """Run a DualSPHysics post-processing tool.

    Available tools: partvtk, partvtkout, isosurface, computeforces,
    flowtool, boundaryvtk, floatinginfo, measuretool.

    The LLM composes the CLI arguments based on the tool's help documentation.

    Args:
        postprocess_tool: Name of the post-processing tool (case-insensitive).
        args:             CLI arguments as a list of strings. Paths should be
                          relative to cwd (e.g. ["out/data", "-savevtk",
                          "out/particles/PartFluid"]).
        cwd:              Working directory. All relative paths in args resolve
                          against this. Typically the run directory.

    Returns dict with returncode, stdout, stderr, output_files.
    """
    logger.info("run_postprocess: tool=%s args=%s cwd=%s", postprocess_tool, args, cwd)
    result = await _run_postprocess(postprocess_tool, args, cwd=cwd)
    logger.info("run_postprocess: returncode=%d output_files=%s",
                result["returncode"], result.get("output_files"))
    return result


@mcp.tool()
async def run_analysis(python_code: str, work_dir: str) -> dict:
    """Execute a Python analysis script on simulation output data.

    The code runs in a subprocess with numpy, matplotlib, and pandas available.
    Use this for parsing CSV files, computing derived quantities (e.g. max
    run-out distance over time), and generating plots.

    Generated files (plots, CSVs) should be saved to work_dir.

    Args:
        python_code: Python source code to execute.
        work_dir:    Working directory (typically the run's output directory).

    Returns dict with returncode, stdout, stderr, output_files.
    """
    logger.info("run_analysis: work_dir=%s code_len=%d", work_dir, len(python_code))
    result = await _run_analysis(python_code, work_dir)
    logger.info("run_analysis: returncode=%d output_files=%s",
                result["returncode"], result.get("output_files"))
    return result


if __name__ == "__main__":
    mcp.run(transport="stdio")
