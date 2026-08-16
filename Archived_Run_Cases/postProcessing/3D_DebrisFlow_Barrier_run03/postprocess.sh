#!/bin/bash
# Post-processing script for DualSPHysics simulation
# Auto-generated — edit freely, then re-run.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="/home/yzhao52/DualSPHysics/DualSPHysics_NN_v5.0.1-danrong-mcp-simulation-agent/dualsphysics-maf/bin/linux"
export LD_LIBRARY_PATH="$BIN_DIR:$LD_LIBRARY_PATH"

# --- Fluid particles → VTK ---
"$BIN_DIR"/PartVTK_linux64 -dirin "$SCRIPT_DIR"/out/data -savevtk "$SCRIPT_DIR"/out/particles/PartFluid -onlytype:-all,+fluid -vars:+idp,+vel,+rhop,+press

# --- Fluid particles → CSV ---
"$BIN_DIR"/PartVTK_linux64 -dirin "$SCRIPT_DIR"/out/data -savecsv "$SCRIPT_DIR"/out/particles/PartFluidCSV -onlytype:-all,+fluid -vars:+idp,+vel,+rhop,+press

# --- Boundary particles → VTK ---
"$BIN_DIR"/PartVTK_linux64 -dirin "$SCRIPT_DIR"/out/data -savevtk "$SCRIPT_DIR"/out/particles/PartBound -onlytype:-all,+bound -vars:+mk,+rhop

# --- Free-surface x-z slice at center-y plane (y=10 m) ---
"$BIN_DIR"/IsoSurface_linux64 -dirin "$SCRIPT_DIR"/out/data -saveslice "$SCRIPT_DIR"/out/particles/IsoSliceY10 -slicevec:0:10:0:0:1:0

# --- Short barrier reaction forces ---
"$BIN_DIR"/ComputeForces_linux64 -dirin "$SCRIPT_DIR"/out/data -filexml AUTO -gravity:0:0:-9.81 -viscoauto: -onlymk:10,11 -onlypos:78.5:-1:0:83.5:21:20 -savecsv "$SCRIPT_DIR"/out/analysis/BarrierForcesShort

# --- Short barrier bending moment about y-axis at barrier base ---
"$BIN_DIR"/ComputeForces_linux64 -dirin "$SCRIPT_DIR"/out/data -filexml AUTO -gravity:0:0:-9.81 -viscoauto: -onlymk:10,11 -onlypos:78.5:-1:0:83.5:21:20 -momentaxis:79:0:0:79:1:0 -savecsv "$SCRIPT_DIR"/out/analysis/BarrierMomentYShort