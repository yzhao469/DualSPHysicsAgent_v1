"""Run MeasureTool to extract probe point data from simulation output."""
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import MEASURETOOL_BIN, TIMEOUT_MEASURETOOL
from tools._subprocess import run_subprocess


async def run_measuretool(data_dir: str, points_file: str, output_csv_stem: str) -> dict:
    """Run MeasureTool on simulation output to extract CSV probe data.

    Args:
        data_dir:         Directory containing the simulation .bi4 part files.
        points_file:      Path to the POINTSLIST file defining probe locations.
        output_csv_stem:  Stem path passed to -savecsv (MeasureTool may append suffixes).

    Returns dict with keys: returncode, stdout, stderr, csv_files (list of found CSVs).
    """
    # Ensure output directory exists
    output_dir = os.path.dirname(output_csv_stem)
    os.makedirs(output_dir, exist_ok=True)

    cmd = [
        MEASURETOOL_BIN,
        "-dirin", data_dir,
        "-points", points_file,
        "-vars:-all,+vel,+rhop",   # MeasureTool uses +vel (all components), not +vel.x
        "-kcusedummy:0",
        "-kclimit:0.5",
        "-savecsv", output_csv_stem,
    ]

    result = await run_subprocess(cmd, timeout=TIMEOUT_MEASURETOOL)

    # Discover actual CSV output files (MeasureTool may append suffixes)
    csv_pattern = os.path.join(output_dir, "*.csv")
    csv_files = sorted(glob.glob(csv_pattern))
    result["csv_files"] = csv_files
    return result
