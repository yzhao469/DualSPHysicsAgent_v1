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
"$BIN_DIR"/PartVTK_linux64 -dirin "$SCRIPT_DIR"/out/data -savecsv "$SCRIPT_DIR"/out/particles/PartFluid -onlytype:-all,+fluid -vars:+idp,+vel,+rhop,+press

# --- Boundary particles → VTK ---
"$BIN_DIR"/PartVTK_linux64 -dirin "$SCRIPT_DIR"/out/data -savevtk "$SCRIPT_DIR"/out/particles/PartBound -onlytype:-all,+bound -vars:+mk,+rhop,+press

# --- Right wall reaction forces → CSV ---
"$BIN_DIR"/ComputeForces_linux64 -dirin "$SCRIPT_DIR"/out/data -filexml AUTO -onlymk:21 -gravity:0:0:-9.81 -viscoauto: -savecsv "$SCRIPT_DIR"/out/analysis/RightWallForces

# --- Right wall only reaction forces (mk + spatial slab) → CSV ---
"$BIN_DIR"/ComputeForces_linux64 -dirin "$SCRIPT_DIR"/out/data -filexml AUTO -onlymk:21 -onlypos:99.75:-100:-100:101.25:100:100 -gravity:0:0:-9.81 -viscoauto: -savecsv "$SCRIPT_DIR"/out/analysis/RightWallOnlyForces

# --- Create pressure probe points file along a vertical line in front of the right wall ---
cat > "$SCRIPT_DIR"/right_wall_probes.txt << 'EOF'
POINTSLIST
99.5 0.0 0.0
99.5 0.0 0.5
99.5 0.0 1.0
99.5 0.0 1.5
99.5 0.0 2.0
99.5 0.0 2.5
99.5 0.0 3.0
99.5 0.0 3.5
99.5 0.0 4.0
99.5 0.0 4.5
99.5 0.0 5.0
99.5 0.0 5.5
99.5 0.0 6.0
99.5 0.0 6.5
99.5 0.0 7.0
99.5 0.0 7.5
99.5 0.0 8.0
99.5 0.0 8.5
99.5 0.0 9.0
99.5 0.0 9.5
99.5 0.0 10.0
EOF

# --- Ensure analysis output directory exists for probe CSV output ---
mkdir -p "$SCRIPT_DIR"/out/analysis

# --- Right wall pressure probes → CSV ---
"$BIN_DIR"/MeasureTool_linux64 -dirin "$SCRIPT_DIR"/out/data -filexml AUTO -points "$SCRIPT_DIR"/right_wall_probes.txt -onlytype:-all,+fluid -vars:+press -savecsv "$SCRIPT_DIR"/out/analysis/RightWallProbePress