"""Run DualSPHysics non-Newtonian solver (CPU or GPU)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import SOLVER_BIN_CPU, SOLVER_BIN_GPU, BIN_DIR, TIMEOUT_SIMULATION
from tools._subprocess import run_subprocess


async def run_simulation(case_path: str, output_dir: str, gpu: bool = False) -> dict:
    """Run DualSPHysics solver.

    Args:
        case_path:  Path to the GenCase output case (e.g. out/CaseDebrisFlow2D),
                    without file extension.
        output_dir: Directory to write simulation output into.
        gpu:        If True, use GPU binary with -gpu flag; else use CPU binary.

    Returns dict with keys: returncode, stdout, stderr, data_dir, gpu.
    """
    os.makedirs(output_dir, exist_ok=True)

    # Build env with LD_LIBRARY_PATH so shared libs are found
    env = os.environ.copy()
    existing_ld = env.get("LD_LIBRARY_PATH", "")
    env["LD_LIBRARY_PATH"] = f"{BIN_DIR}:{existing_ld}" if existing_ld else BIN_DIR

    if gpu:
        cmd = [SOLVER_BIN_GPU, "-gpu", case_path, output_dir,
               "-dirdataout", "data", "-svres"]
    else:
        cmd = [SOLVER_BIN_CPU, case_path, output_dir,
               "-dirdataout", "data", "-svres"]

    result = await run_subprocess(cmd, timeout=TIMEOUT_SIMULATION, env=env)
    result["data_dir"] = os.path.join(output_dir, "data")
    result["gpu"] = gpu
    return result
