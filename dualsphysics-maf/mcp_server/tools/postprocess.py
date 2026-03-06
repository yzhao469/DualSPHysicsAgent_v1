"""Generic post-processing tool wrapper for DualSPHysics CLI binaries.

Supports: PartVTK, PartVTKOut, IsoSurface, ComputeForces, FlowTool,
BoundaryVTK, FloatingInfo, MeasureTool.
"""

import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (
    BIN_DIR,
    BOUNDARYVTK_BIN,
    COMPUTEFORCES_BIN,
    FLOATINGINFO_BIN,
    FLOWTOOL_BIN,
    ISOSURFACE_BIN,
    MEASURETOOL_BIN,
    PARTVTK_BIN,
    PARTVTKOUT_BIN,
    TIMEOUT_POSTPROCESS,
)
from tools._subprocess import run_subprocess

_TOOL_BINS = {
    "partvtk": PARTVTK_BIN,
    "partvtkout": PARTVTKOUT_BIN,
    "isosurface": ISOSURFACE_BIN,
    "computeforces": COMPUTEFORCES_BIN,
    "flowtool": FLOWTOOL_BIN,
    "boundaryvtk": BOUNDARYVTK_BIN,
    "floatinginfo": FLOATINGINFO_BIN,
    "measuretool": MEASURETOOL_BIN,
}


async def run_postprocess(tool_name: str, args: list[str], cwd: str | None = None) -> dict:
    """Run a DualSPHysics post-processing tool.

    Args:
        tool_name: One of partvtk, partvtkout, isosurface, computeforces,
                   flowtool, boundaryvtk, floatinginfo, measuretool.
        args:      CLI arguments as a list of strings.
        cwd:       Working directory for the subprocess. All relative paths
                   in args are resolved relative to this directory.

    Returns dict with returncode, stdout, stderr, output_files.
    """
    tool_name = tool_name.lower().strip()
    binary = _TOOL_BINS.get(tool_name)
    if binary is None:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": f"Unknown tool: {tool_name}. Available: {list(_TOOL_BINS.keys())}",
            "output_files": [],
        }

    # Collect output paths from args (look for -savevtk, -savecsv, etc.)
    # Handles both "-savevtk path" (two args) and "-savecsv:path" (colon-joined)
    output_stems = []
    for i, arg in enumerate(args):
        if arg.startswith("-save") or arg.startswith("-SaveResume"):
            if ":" in arg:
                # Colon-joined format: -savecsv:path/to/output
                _, _, path = arg.partition(":")
                if path:
                    output_stems.append(path)
            elif i + 1 < len(args) and not args[i + 1].startswith("-"):
                output_stems.append(args[i + 1])

    env = os.environ.copy()
    existing_ld = env.get("LD_LIBRARY_PATH", "")
    env["LD_LIBRARY_PATH"] = f"{BIN_DIR}:{existing_ld}" if existing_ld else BIN_DIR

    cmd = [binary] + args
    result = await run_subprocess(cmd, timeout=TIMEOUT_POSTPROCESS, env=env, cwd=cwd)

    # Discover generated output files from the stems
    # Resolve relative stems against cwd for glob matching
    output_files = []
    for stem in output_stems:
        abs_stem = os.path.join(cwd, stem) if cwd and not os.path.isabs(stem) else stem
        parent = os.path.dirname(abs_stem) or "."
        base = os.path.basename(abs_stem)
        # Tools append suffixes like _0000.vtk, _Vel.csv, etc.
        pattern = os.path.join(parent, f"{base}*")
        output_files.extend(sorted(glob.glob(pattern)))

    result["output_files"] = output_files
    return result
