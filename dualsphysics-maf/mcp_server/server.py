"""DualSPHysics MCP Server — 5 tools for SPH simulation control."""
import logging
import os
import sys

# Ensure the mcp_server package is importable when run as __main__
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp.server.fastmcp import FastMCP

from tools.xml_modifier import modify_xml as _modify_xml
from tools.run_gencase import run_gencase as _run_gencase
from tools.run_simulation import run_simulation as _run_simulation
from tools.run_measuretool import run_measuretool as _run_measuretool
from tools.metrics import compute_metrics as _compute_metrics

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
def modify_xml(
    base_xml: str,
    output_xml: str,
    dp: float | None = None,
    coefh: float | None = None,
    cflnumber: float | None = None,
    Visco: float | None = None,
    DensityDT: int | None = None,
    DensityDTvalue: float | None = None,
    TimeMax: float | None = None,
    TimeOut: float | None = None,
    visco_nn: float | None = None,
    tau_yield: float | None = None,
    HBP_m: float | None = None,
    HBP_n: float | None = None,
) -> str:
    """Copy base_xml to output_xml and apply the provided simulation parameters.

    Only parameters that are explicitly provided (non-None) are modified.
    Returns the path to the output XML file.
    """
    changed = {k: v for k, v in locals().items()
               if v is not None and k not in ("base_xml", "output_xml")}
    logger.info("modify_xml: base=%s output=%s params=%s", base_xml, output_xml, changed)

    result = _modify_xml(
        base_xml=base_xml,
        output_xml=output_xml,
        dp=dp,
        coefh=coefh,
        cflnumber=cflnumber,
        Visco=Visco,
        DensityDT=DensityDT,
        DensityDTvalue=DensityDTvalue,
        TimeMax=TimeMax,
        TimeOut=TimeOut,
        visco_nn=visco_nn,
        tau_yield=tau_yield,
        HBP_m=HBP_m,
        HBP_n=HBP_n,
    )
    logger.info("modify_xml: done → %s", result)
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


if __name__ == "__main__":
    mcp.run(transport="stdio")
