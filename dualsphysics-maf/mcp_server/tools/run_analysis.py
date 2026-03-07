"""Execute Python analysis scripts on simulation output data.

Runs user-generated Python code in a subprocess with numpy/matplotlib
available. The code operates in a specified working directory and can
read CSV/VTK files and produce plots or derived data files.
"""

import asyncio
import glob
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import TIMEOUT_ANALYSIS


async def run_analysis(python_code: str, work_dir: str) -> dict:
    """Execute a Python analysis script.

    Args:
        python_code: Python source code to execute. The code runs with
                     ``work_dir`` as cwd and can import numpy, matplotlib, etc.
                     Generated files (plots, CSVs) should be saved to ``work_dir``.
        work_dir:    Working directory for the script.

    Returns dict with returncode, stdout, stderr, output_files.
    """
    os.makedirs(work_dir, exist_ok=True)

    # Snapshot files before execution
    before = set(glob.glob(os.path.join(work_dir, "**", "*"), recursive=True))

    # Write code to a temp file in work_dir
    script_path = os.path.join(work_dir, "_analysis_script.py")
    with open(script_path, "w") as f:
        f.write(python_code)

    # Determine which Python to use (same venv as the server)
    python_bin = sys.executable

    try:
        proc = await asyncio.create_subprocess_exec(
            python_bin, script_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=work_dir,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=TIMEOUT_ANALYSIS
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": f"Analysis script timed out after {TIMEOUT_ANALYSIS}s",
                "output_files": [],
            }

        # Discover new files created by the script
        after = set(glob.glob(os.path.join(work_dir, "**", "*"), recursive=True))
        new_files = sorted(after - before - {script_path})

        return {
            "returncode": proc.returncode,
            "stdout": stdout.decode(errors="replace"),
            "stderr": stderr.decode(errors="replace"),
            "output_files": new_files,
        }
    except Exception as e:
        return {"returncode": -1, "stdout": "", "stderr": str(e), "output_files": []}
    finally:
        # Clean up the temp script
        if os.path.exists(script_path):
            os.remove(script_path)
