import os

BASE_DIR        = "/home/danrong/projects/DualSPHysics_NN_v5.0.1"
BIN_DIR         = f"{BASE_DIR}/bin/linux"

GENCASE_BIN     = f"{BIN_DIR}/GenCase_linux64"
SOLVER_BIN_CPU  = f"{BIN_DIR}/DualSPHysics5.0_NNewtonianCPU_linux64"
SOLVER_BIN_GPU  = f"{BIN_DIR}/DualSPHysics5.0_NNewtonian_linux64"
MEASURETOOL_BIN = f"{BIN_DIR}/MeasureTool_linux64"

PROJECT_DIR      = f"{BASE_DIR}/dualsphysics-maf"
RUNS_DIR         = f"{PROJECT_DIR}/runs"
CASES_DIR        = f"{PROJECT_DIR}/cases"
BASE_XML         = f"{CASES_DIR}/BaseCase_Def.xml"
LEGACY_XML       = f"{CASES_DIR}/CaseDebrisFlow2D_Def.xml"
POINTS_FILE      = f"{CASES_DIR}/CaseDebrisFlow2D_Points.txt"
GROUND_TRUTH_CSV = f"{CASES_DIR}/ground_truth/PointsMeasure.csv"

# Subprocess timeouts (seconds)
TIMEOUT_GENCASE     = 300     # 5 min
TIMEOUT_SIMULATION  = 7200    # 2 hours (SPH can be slow)
TIMEOUT_MEASURETOOL = 300     # 5 min
