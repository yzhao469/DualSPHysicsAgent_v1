#!/bin/bash
# Post-processing script for DualSPHysics simulation
# Auto-generated — edit freely, then re-run.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="/home/yzhao52/DualSPHysics/DualSPHysics_NN_v5.0.1-danrong-mcp-simulation-agent/dualsphysics-maf/bin/linux"
export LD_LIBRARY_PATH="$BIN_DIR:$LD_LIBRARY_PATH"

# --- Fluid particles → VTK ---
"$BIN_DIR"/PartVTK_linux64 -dirin "$SCRIPT_DIR"/out/data -savevtk "$SCRIPT_DIR"/out/particles/PartFluid -onlytype:-all,+fluid -vars:+idp,+vel,+rhop,+press

# --- Fluid particles → CSV (positions for contact-time analysis) ---
"$BIN_DIR"/PartVTK_linux64 -dirin "$SCRIPT_DIR"/out/data -savecsv "$SCRIPT_DIR"/out/particles/PartFluidPos -onlytype:-all,+fluid -vars:+idp

# --- Boundary particles → VTK ---
"$BIN_DIR"/PartVTK_linux64 -dirin "$SCRIPT_DIR"/out/data -savevtk "$SCRIPT_DIR"/out/particles/PartBound -onlytype:-all,+bound -vars:+mk,+rhop

# --- Fluid free surface → XZ slice at y=10 m ---
"$BIN_DIR"/IsoSurface_linux64 -dirin "$SCRIPT_DIR"/out/data -saveslice "$SCRIPT_DIR"/out/analysis/isosurface_xz_y10/SliceXZ_y10 -slicevec:0:10:0:0:1:0 -onlytype:-all,+fluid

# --- Barrier boundary force time history → CSV ---
"$BIN_DIR"/ComputeForces_linux64 -dirin "$SCRIPT_DIR"/out/data -filexml AUTO -gravity:0:0:-9.81 -onlymk:11 -savecsv "$SCRIPT_DIR"/out/analysis/barrier_forces

# --- Barrier base bending moment about horizontal y-axis through barrier toe → CSV ---
"$BIN_DIR"/ComputeForces_linux64 -dirin "$SCRIPT_DIR"/out/data -filexml AUTO -gravity:0:0:-9.81 -onlymk:11 -momentaxis:81:0:0:81:1:0 -savecsv "$SCRIPT_DIR"/out/analysis/barrier_moment_base