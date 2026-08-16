#!/bin/bash
# Post-processing script for DualSPHysics simulation
# Auto-generated — edit freely, then re-run.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="/home/yzhao52/DualSPHysics/DualSPHysics_NN_v5.0.1-danrong-mcp-simulation-agent/dualsphysics-maf/bin/linux"
export LD_LIBRARY_PATH="$BIN_DIR:$LD_LIBRARY_PATH"

# --- Fluid particles → VTK ---
"$BIN_DIR"/PartVTK_linux64 -dirin "$SCRIPT_DIR"/out/data -savevtk "$SCRIPT_DIR"/out/particles/PartFluid -onlytype:-all,+fluid -vars:+idp,+mk,+vel,+rhop,+press

# --- Fluid particles → CSV ---
"$BIN_DIR"/PartVTK_linux64 -dirin "$SCRIPT_DIR"/out/data -savecsv "$SCRIPT_DIR"/out/particles/PartFluidCsv -onlytype:-all,+fluid -vars:+idp,+mk,+vel,+rhop,+press

# --- Boundary particles → VTK ---
"$BIN_DIR"/PartVTK_linux64 -dirin "$SCRIPT_DIR"/out/data -savevtk "$SCRIPT_DIR"/out/particles/PartBound -onlytype:-all,+bound -vars:+mk,+rhop

# --- IsoSurface slice for top fluid phase (mk=1) ---
"$BIN_DIR"/IsoSurface_linux64 -dirin "$SCRIPT_DIR"/out/data -saveslice "$SCRIPT_DIR"/out/particles/IsoTop -onlytype:-all,+fluid -onlymk:1 -vars:+mk

# --- IsoSurface slice for bottom fluid phase (mk=2) ---
"$BIN_DIR"/IsoSurface_linux64 -dirin "$SCRIPT_DIR"/out/data -saveslice "$SCRIPT_DIR"/out/particles/IsoBottom -onlytype:-all,+fluid -onlymk:2 -vars:+mk