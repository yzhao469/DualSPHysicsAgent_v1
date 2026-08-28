#!/bin/bash
# Post-processing script for DualSPHysics simulation
# Auto-generated — edit freely, then re-run.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="/mnt/c/Users/yzhao52/OneDrive - University of Nebraska/Student Research/Undergraduates research/AI-agent DualSPHysics Debris Flow/agent_v1/Github/dualsphysics-maf/bin/linux"
export LD_LIBRARY_PATH="$BIN_DIR:$LD_LIBRARY_PATH"

# --- Fluid particles → VTK ---
"$BIN_DIR"/PartVTK_linux64 -dirin "$SCRIPT_DIR"/out/data -savevtk "$SCRIPT_DIR"/out/particles/PartFluid -onlytype:-all,+fluid -vars:+idp,+vel,+rhop,+press

# --- Boundary particles → VTK ---
"$BIN_DIR"/PartVTK_linux64 -dirin "$SCRIPT_DIR"/out/data -savevtk "$SCRIPT_DIR"/out/particles/PartBound -onlytype:-all,+bound -vars:+mk,+rhop

# --- Compute forces for all flexible gate boundary groups combined ---
"$BIN_DIR"/ComputeForces_linux64 -dirin "$SCRIPT_DIR"/out/data -gravity:0:0:-9.81 -viscoauto: -onlymk:11,12,13,14,15 -savecsv "$SCRIPT_DIR"/out/analysis/ForcesGateAll.csv

# --- Compute forces for flexible gate segment mk11 ---
"$BIN_DIR"/ComputeForces_linux64 -dirin "$SCRIPT_DIR"/out/data -gravity:0:0:-9.81 -viscoauto: -onlymk:11 -savecsv "$SCRIPT_DIR"/out/analysis/ForcesGate_mk11.csv

# --- Compute forces for flexible gate segment mk12 ---
"$BIN_DIR"/ComputeForces_linux64 -dirin "$SCRIPT_DIR"/out/data -gravity:0:0:-9.81 -viscoauto: -onlymk:12 -savecsv "$SCRIPT_DIR"/out/analysis/ForcesGate_mk12.csv

# --- Compute forces for flexible gate segment mk13 ---
"$BIN_DIR"/ComputeForces_linux64 -dirin "$SCRIPT_DIR"/out/data -gravity:0:0:-9.81 -viscoauto: -onlymk:13 -savecsv "$SCRIPT_DIR"/out/analysis/ForcesGate_mk13.csv

# --- Compute forces for flexible gate segment mk14 ---
"$BIN_DIR"/ComputeForces_linux64 -dirin "$SCRIPT_DIR"/out/data -gravity:0:0:-9.81 -viscoauto: -onlymk:14 -savecsv "$SCRIPT_DIR"/out/analysis/ForcesGate_mk14.csv

# --- Compute forces for flexible gate segment mk15 ---
"$BIN_DIR"/ComputeForces_linux64 -dirin "$SCRIPT_DIR"/out/data -gravity:0:0:-9.81 -viscoauto: -onlymk:15 -savecsv "$SCRIPT_DIR"/out/analysis/ForcesGate_mk15.csv