"""Run GenCase to generate initial particle configuration."""
import os
import sys

# Allow importing config from parent package when run standalone
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import GENCASE_BIN, TIMEOUT_GENCASE
from tools._subprocess import run_subprocess


async def run_gencase(xml_path: str, output_dir: str) -> dict:
    """Run GenCase on xml_path (without .xml extension), writing output to output_dir.

    Args:
        xml_path:   Path to the XML file WITHOUT the .xml extension.
        output_dir: Directory where GenCase output files will be written.

    Returns dict with keys: returncode, stdout, stderr, output_dir.
    """
    os.makedirs(output_dir, exist_ok=True)

    # Case name is derived from the xml_path basename
    case_name = os.path.basename(xml_path)
    output_case = os.path.join(output_dir, case_name)

    cmd = [GENCASE_BIN, xml_path, output_case, "-save:all"]

    result = await run_subprocess(cmd, timeout=TIMEOUT_GENCASE)
    result["output_dir"] = output_dir
    return result
