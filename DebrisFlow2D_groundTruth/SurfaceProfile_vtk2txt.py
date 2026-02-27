"""
Convert all Slices_phase1_*.vtk files to individual .txt files
containing particle positions (X Y Z).

Usage:
    python convert_slices_vtk.py

Edit INPUT_DIR and OUTPUT_DIR below to match your paths.
"""

import numpy as np
import glob
import os

# ── USER SETTINGS ─────────────────────────────────────────────────────────────
INPUT_DIR  = "/home/yzhao52/DualSPHysics/DualSPHysics_NN_v5.0.1-danrong-mcp-simulation-agent/examples/mphase_nnewtonian/DebrisFlow2D/CaseDebrisFlow2D_out/surface"        # folder containing Slices_phase1_*.vtk
OUTPUT_DIR = "/home/yzhao52/DualSPHysics/DualSPHysics_NN_v5.0.1-danrong-mcp-simulation-agent/examples/mphase_nnewtonian/DebrisFlow2D/CaseDebrisFlow2D_out/surface" # folder to save .txt files (created if missing)
# ──────────────────────────────────────────────────────────────────────────────

def parse_vtk_points(filepath):
    """
    Parse a binary VTK POLYDATA file and return an (N, 3) numpy array
    of particle positions.
    Supports float (32-bit) and double (64-bit) point data.
    """
    with open(filepath, 'rb') as f:
        # Read ASCII header until we hit the POINTS line
        while True:
            line = f.readline().decode('ascii', errors='replace').strip()
            if line.startswith('POINTS'):
                parts = line.split()
                n_points  = int(parts[1])
                dtype_str = parts[2].lower()   # 'float' or 'double'
                break

        # VTK binary is big-endian
        if dtype_str == 'float':
            dt = np.dtype('>f4')
        elif dtype_str == 'double':
            dt = np.dtype('>f8')
        else:
            raise ValueError(f"Unsupported VTK point type: {dtype_str}")

        raw  = f.read(n_points * 3 * dt.itemsize)
        coords = np.frombuffer(raw, dtype=dt).reshape((n_points, 3))

    return coords


def convert_all():
    # Make sure output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Find all matching VTK files, sorted numerically
    pattern = os.path.join(INPUT_DIR, "Slices_phase1_*.vtk")
    vtk_files = sorted(glob.glob(pattern))

    if not vtk_files:
        print(f"No files found matching: {pattern}")
        return

    print(f"Found {len(vtk_files)} VTK file(s) in: {INPUT_DIR}")
    print(f"Output will be written to: {OUTPUT_DIR}\n")

    for vtk_path in vtk_files:
        basename    = os.path.splitext(os.path.basename(vtk_path))[0]  # e.g. Slices_phase1_0017
        output_path = os.path.join(OUTPUT_DIR, basename + "_positions.txt")

        try:
            coords = parse_vtk_points(vtk_path)

            with open(output_path, 'w') as f:
                f.write(f"# Particle positions extracted from {os.path.basename(vtk_path)}\n")
                f.write(f"# Total particles: {len(coords)}\n")
                f.write(f"# Columns: X  Y  Z\n")
                for x, y, z in coords:
                    f.write(f"{x:.8f}  {y:.8f}  {z:.8f}\n")

            print(f"  [OK] {os.path.basename(vtk_path)} -> {os.path.basename(output_path)}  ({len(coords)} particles)")

        except Exception as e:
            print(f"  [ERROR] {os.path.basename(vtk_path)}: {e}")

    print("\nDone.")


if __name__ == "__main__":
    convert_all()