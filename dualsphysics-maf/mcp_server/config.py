import os
from pathlib import Path

_THIS_FILE = Path(__file__).resolve()
_DEFAULT_WORKSPACE_ROOT = _THIS_FILE.parents[2]
_DEFAULT_PROJECT_DIR = _THIS_FILE.parents[1]


def _resolve_dualsphysics_root() -> Path:
	"""Resolve DualSPHysics install root that contains bin/linux binaries.

	Priority:
	  1) DUALSPHYSICS_ROOT env var
	  2) Legacy co-located workspace layout (parents[2])
	  3) Known user-local install location under ~/DualSPHysics
	  4) Fallback to parents[2]
	"""
	env_root = os.getenv("DUALSPHYSICS_ROOT")
	if env_root:
		return Path(env_root).expanduser().resolve()

	legacy_root = _DEFAULT_WORKSPACE_ROOT
	legacy_gencase = legacy_root / "bin" / "linux" / "GenCase_linux64"
	if legacy_gencase.exists():
		return legacy_root

	user_local_root = (
		Path.home()
		/ "DualSPHysics"
		/ "DualSPHysics_NN_v5.0.1-danrong-mcp-simulation-agent"
	)
	user_local_gencase = user_local_root / "bin" / "linux" / "GenCase_linux64"
	if user_local_gencase.exists():
		return user_local_root

	return legacy_root


DUALSPHYSICS_ROOT = _resolve_dualsphysics_root()
PROJECT_DIR_PATH = Path(os.getenv("DUALSPHYSICS_MAF_DIR", str(_DEFAULT_PROJECT_DIR))).expanduser().resolve()

BASE_DIR        = str(DUALSPHYSICS_ROOT)
BIN_DIR         = f"{DUALSPHYSICS_ROOT}/bin/linux"

GENCASE_BIN      = f"{BIN_DIR}/GenCase_linux64"
SOLVER_BIN_CPU   = f"{BIN_DIR}/DualSPHysics5.0_NNewtonianCPU_linux64"
SOLVER_BIN_GPU   = f"{BIN_DIR}/DualSPHysics5.0_NNewtonian_linux64"
MEASURETOOL_BIN  = f"{BIN_DIR}/MeasureTool_linux64"

# Post-processing binaries
PARTVTK_BIN      = f"{BIN_DIR}/PartVTK_linux64"
PARTVTKOUT_BIN   = f"{BIN_DIR}/PartVTKOut_linux64"
ISOSURFACE_BIN   = f"{BIN_DIR}/IsoSurface_linux64"
COMPUTEFORCES_BIN = f"{BIN_DIR}/ComputeForces_linux64"
FLOWTOOL_BIN     = f"{BIN_DIR}/FlowTool_linux64"
BOUNDARYVTK_BIN  = f"{BIN_DIR}/BoundaryVTK_linux64"
FLOATINGINFO_BIN = f"{BIN_DIR}/FloatingInfo_linux64"

PROJECT_DIR      = str(PROJECT_DIR_PATH)
RUNS_DIR         = f"{PROJECT_DIR}/runs"
CASES_DIR        = f"{PROJECT_DIR}/cases"
BASE_XML         = f"{CASES_DIR}/BaseCase_Def.xml"
LEGACY_XML       = f"{CASES_DIR}/CaseDebrisFlow2D_Def.xml"

# Subprocess timeouts (seconds)
TIMEOUT_GENCASE      = 300     # 5 min
TIMEOUT_SIMULATION   = 7200    # 2 hours (SPH can be slow)
TIMEOUT_POSTPROCESS  = 600     # 10 min
TIMEOUT_ANALYSIS     = 120     # 2 min for Python analysis scripts
