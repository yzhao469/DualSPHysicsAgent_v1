#!/bin/bash
# Post-processing script for DualSPHysics simulation
# Auto-generated — edit freely, then re-run.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="/home/yzhao52/DualSPHysics/DualSPHysics_NN_v5.0.1-danrong-mcp-simulation-agent/dualsphysics-maf/bin/linux"
export LD_LIBRARY_PATH="$BIN_DIR:$LD_LIBRARY_PATH"

# --- Prepare analysis directory ---
mkdir -p "$SCRIPT_DIR"/out/analysis

# --- Generate FlowTool boxes template for reference ---
"$BIN_DIR"/FlowTool_linux64 -boxestemplate -savecsv "$SCRIPT_DIR"/out/analysis/flowtool_template

# --- Print generated FlowTool template to help verify exact boxes syntax ---
cat "$SCRIPT_DIR"/out/analysis/flowtool_template.boxes

# --- Create trench-outlet flux section boxes file using template-compatible syntax ---
cat > "$SCRIPT_DIR"/out/analysis/boxes_outlet.dat << 'EOF'
# Trench-outlet flux section prism centered near outlet candidate.
# Center: (0.3340375, 0.0, 0.0208031)
# Local axes:
#   u = (0.9209894, 0, -0.3895876)
#   v = (0, 1, 0)
#   w = (0.3895876, 0, 0.9209894)
# Half-lengths:
#   hu = 0.0504
#   hv = 0.20
#   hw = 0.15
#
# Prism corners adapted to FlowTool template-compatible 8-point box syntax:
# p1 = c - hu*u - hv*v - hw*w = (0.2290, -0.2000, -0.0970)
# p2 = c + hu*u - hv*v - hw*w = (0.3218, -0.2000, -0.1363)
# p3 = c + hu*u + hv*v - hw*w = (0.3218,  0.2000, -0.1363)
# p4 = c - hu*u + hv*v - hw*w = (0.2290,  0.2000, -0.0970)
# p5 = c - hu*u - hv*v + hw*w = (0.3459, -0.2000,  0.1799)
# p6 = c + hu*u - hv*v + hw*w = (0.4387, -0.2000,  0.1406)
# p7 = c + hu*u + hv*v + hw*w = (0.4387,  0.2000,  0.1406)
# p8 = c - hu*u + hv*v + hw*w = (0.3459,  0.2000,  0.1799)
#
#FmtVersion 1
#NumBoxes 1
#
#Box outlet_section
0.2290 -0.2000 -0.0970
0.3218 -0.2000 -0.1363
0.3218 0.2000 -0.1363
0.2290 0.2000 -0.0970
0.3459 -0.2000 0.1799
0.4387 -0.2000 0.1406
0.4387 0.2000 0.1406
0.3459 0.2000 0.1799
EOF

# --- Compute outlet flow rate with FlowTool ---
"$BIN_DIR"/FlowTool_linux64 -dirin "$SCRIPT_DIR"/out/data -fileboxes "$SCRIPT_DIR"/out/analysis/boxes_outlet.dat -savecsv "$SCRIPT_DIR"/out/analysis/flow_outlet

# --- Fluid particles → VTK ---
"$BIN_DIR"/PartVTK_linux64 -dirin "$SCRIPT_DIR"/out/data -savevtk "$SCRIPT_DIR"/out/particles/PartFluid -onlytype:-all,+fluid -vars:+idp,+vel,+rhop,+press

# --- Boundary particles → VTK ---
"$BIN_DIR"/PartVTK_linux64 -dirin "$SCRIPT_DIR"/out/data -savevtk "$SCRIPT_DIR"/out/particles/PartBound -onlytype:-all,+bound -vars:+mk,+rhop

# --- Generate longitudinal center-plane isosurface slices at y=0 for time-snapshot comparison ---
"$BIN_DIR"/IsoSurface_linux64 -dirin "$SCRIPT_DIR"/out/data -onlytype:-all,+fluid -vars:+vel -saveslice "$SCRIPT_DIR"/out/analysis/iso_centerline -slicevec:0:0:0:0:1:0 -createdirs:1