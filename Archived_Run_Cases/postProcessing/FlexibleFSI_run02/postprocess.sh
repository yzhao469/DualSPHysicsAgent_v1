#!/bin/bash
# Post-processing script for DualSPHysics simulation
# Auto-generated — edit freely, then re-run.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="/mnt/c/Users/yzhao52/OneDrive - University of Nebraska/My Research/AI-agent DualSPHysics Debris Flow/agent_v1/Github/dualsphysics-maf/bin/linux"
export LD_LIBRARY_PATH="$BIN_DIR:$LD_LIBRARY_PATH"

# --- Fluid particles → VTK ---
"$BIN_DIR"/PartVTK_linux64 -dirin "$SCRIPT_DIR"/out/data -savevtk "$SCRIPT_DIR"/out/particles/PartFluid -onlytype:-all,+fluid -vars:+idp,+vel,+rhop,+press

# --- Boundary particles → VTK ---
"$BIN_DIR"/PartVTK_linux64 -dirin "$SCRIPT_DIR"/out/data -savevtk "$SCRIPT_DIR"/out/particles/PartBound -onlytype:-all,+bound -vars:+mk,+rhop

# --- Boundary particles → CSV (track gate particle identity over time) ---
"$BIN_DIR"/PartVTK_linux64 -dirin "$SCRIPT_DIR"/out/data -savecsv "$SCRIPT_DIR"/out/particles/PartBoundCsv -onlytype:-all,+bound -vars:+idp,+mk,+rhop

# --- Compute forces on flexible gate segment mk 11 ---
"$BIN_DIR"/ComputeForces_linux64 -dirin "$SCRIPT_DIR"/out/data -onlymk:11 -savecsv "$SCRIPT_DIR"/out/analysis/GateForce_mk11

# --- Compute forces on flexible gate segment mk 12 ---
"$BIN_DIR"/ComputeForces_linux64 -dirin "$SCRIPT_DIR"/out/data -onlymk:12 -savecsv "$SCRIPT_DIR"/out/analysis/GateForce_mk12

# --- Compute forces on flexible gate segment mk 13 ---
"$BIN_DIR"/ComputeForces_linux64 -dirin "$SCRIPT_DIR"/out/data -onlymk:13 -savecsv "$SCRIPT_DIR"/out/analysis/GateForce_mk13

# --- Compute forces on flexible gate segment mk 14 ---
"$BIN_DIR"/ComputeForces_linux64 -dirin "$SCRIPT_DIR"/out/data -onlymk:14 -savecsv "$SCRIPT_DIR"/out/analysis/GateForce_mk14

# --- Compute forces on flexible gate segment mk 15 ---
"$BIN_DIR"/ComputeForces_linux64 -dirin "$SCRIPT_DIR"/out/data -onlymk:15 -savecsv "$SCRIPT_DIR"/out/analysis/GateForce_mk15