#!/bin/bash
# Post-processing script for DualSPHysics simulation
# Auto-generated — edit freely, then re-run.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="/home/yzhao52/DualSPHysics/DualSPHysics_NN_v5.0.1-danrong-mcp-simulation-agent/dualsphysics-maf/bin/linux"
export LD_LIBRARY_PATH="$BIN_DIR:$LD_LIBRARY_PATH"

# --- Ensure output directories exist ---
mkdir -p "$SCRIPT_DIR"/out/particles
mkdir -p "$SCRIPT_DIR"/out/analysis
mkdir -p "$SCRIPT_DIR"/out/analysis/isosurface

# --- Fluid particles → VTK ---
"$BIN_DIR"/PartVTK_linux64 -dirin "$SCRIPT_DIR"/out/data -savevtk "$SCRIPT_DIR"/out/particles/PartFluid -onlytype:-all,+fluid -vars:+idp,+vel,+rhop,+press

# --- Fluid particles → CSV ---
"$BIN_DIR"/PartVTK_linux64 -dirin "$SCRIPT_DIR"/out/data -savecsv "$SCRIPT_DIR"/out/particles/PartFluidCsv -onlytype:-all,+fluid -vars:+idp,+vel,+rhop,+press

# --- Boundary particles → VTK ---
"$BIN_DIR"/PartVTK_linux64 -dirin "$SCRIPT_DIR"/out/data -savevtk "$SCRIPT_DIR"/out/particles/PartBound -onlytype:-all,+bound -vars:+mk,+rhop

# --- Boundary particles → CSV ---
"$BIN_DIR"/PartVTK_linux64 -dirin "$SCRIPT_DIR"/out/data -savecsv "$SCRIPT_DIR"/out/particles/PartBoundCsv -onlytype:-all,+bound -vars:+mk,+rhop

# --- Free-surface isosurface reconstruction ---
"$BIN_DIR"/IsoSurface_linux64 -dirin "$SCRIPT_DIR"/out/data -saveiso "$SCRIPT_DIR"/out/analysis/isosurface/FreeSurface -onlytype:-all,+fluid || true

# --- Free-surface profile slice reconstruction (center plane y=0) ---
"$BIN_DIR"/IsoSurface_linux64 -dirin "$SCRIPT_DIR"/out/data -saveslice "$SCRIPT_DIR"/out/analysis/isosurface/FreeSurfaceSlice_Y0 -slicevec:0:0:0:0:1:0 -onlytype:-all,+fluid || true

# --- FlowTool boxes template (reference only; useful for confirming local file format) ---
"$BIN_DIR"/FlowTool_linux64 -boxestemplate > "$SCRIPT_DIR"/out/analysis/flow_boxes_template.txt || true

# --- Define outlet cross-section control volume for trench discharge ---
# Placeholder thin prism near the trench outlet / transition to flat plate.
# The trench is rotated about the Y axis by 23 deg, so this box is oriented
# approximately with a plane perpendicular to the trench axis using the same angle.
# If FlowTool box syntax differs in this build, the command below may fail; the
# fluid CSV export above is kept for downstream custom mass-flux analysis.
cat > "$SCRIPT_DIR"/out/analysis/flow_outlet_boxes.txt << 'EOF'
# Outlet cross-section control volume for FlowTool
# Intended use: thin prism at trench end where inclined trench meets flat bottom plate.
# Placeholder geometry based on available case extents:
# - center near outlet transition around x≈0, y≈0, z≈0.10
# - thin thickness along trench axis
# - width spans trench lateral direction
# - height spans expected flow depth
#
# Adjust this file if needed after checking flow_boxes_template.txt generated above.
#
# Generic single-box definition (placeholder)
BOX 0
CENTER 0.0 0.0 0.10
SIZE 0.08 0.30 0.40
ROTATE 0.0 23.0 0.0
EOF

# --- Compute outlet flow rate / mass-volume flux with FlowTool ---
"$BIN_DIR"/FlowTool_linux64 -dirin "$SCRIPT_DIR"/out/data -fileboxes "$SCRIPT_DIR"/out/analysis/flow_outlet_boxes.txt -savecsv "$SCRIPT_DIR"/out/analysis/flow_outlet.csv -savevtk "$SCRIPT_DIR"/out/analysis/flow_outlet || true