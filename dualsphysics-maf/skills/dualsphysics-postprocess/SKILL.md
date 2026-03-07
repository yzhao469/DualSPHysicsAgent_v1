---
name: dualsphysics-postprocess
description: Post-processing tools for analyzing DualSPHysics simulation output. Covers particle export (PartVTK), surface reconstruction (IsoSurface), force computation, flow rates, and custom Python analysis.
---

# DualSPHysics Post-Processing Reference

After a DualSPHysics simulation completes, raw binary data (`.bi4` files) is
stored in the `data/` subdirectory. Post-processing tools convert this raw data
into human-readable formats (VTK, CSV) for visualization and analysis.

## Available Tools

Use `run_postprocess(tool_name, args)` to call any of these. The `args` list
contains CLI flags exactly as documented in the help resources below.

| Tool | Purpose | Key outputs |
|---|---|---|
| **partvtk** | Extract particles, filter by type/mk/position, compute derived vars | `.vtk`, `.csv` |
| **partvtkout** | Extract excluded/escaped particles | `.vtk`, `.csv` |
| **isosurface** | Reconstruct free surface mesh, compute slices | `.vtk` |
| **measuretool** | Interpolate fields at probe points | `.csv` |
| **computeforces** | Forces and moments on boundaries by mk | `.csv` |
| **flowtool** | Flow rates through defined box regions | `.csv`, `.vtk` |
| **boundaryvtk** | Animate moving/floating boundaries | `.vtk`, `.ply` |
| **floatinginfo** | Floating body motion and forces | `.csv` |

## Common Patterns

### Export fluid particles as VTK (for ParaView visualization)
```
tool_name: partvtk
args: ["-dirin", "<data_dir>", "-savevtk", "<out_dir>/PartFluid",
       "-onlytype:-all,+fluid", "-vars:+idp,+vel,+rhop,+press"]
```

### Export fluid particles as CSV (for data analysis)
```
tool_name: partvtk
args: ["-dirin", "<data_dir>", "-savecsv", "<out_dir>/PartFluid",
       "-onlytype:-all,+fluid", "-vars:+idp,+vel,+rhop,+press"]
```

### Export boundary particles
```
tool_name: partvtk
args: ["-dirin", "<data_dir>", "-savevtk", "<out_dir>/PartBound",
       "-onlytype:-all,+bound", "-vars:+mk,+rhop"]
```

### Export excluded particles (escaped the domain)
```
tool_name: partvtkout
args: ["-dirin", "<data_dir>", "-savevtk", "<out_dir>/PartFluidOut",
       "-SaveResume", "<out_dir>/_ResumeFluidOut"]
```

### Reconstruct free surface (2D slice)
```
tool_name: isosurface
args: ["-dirin", "<data_dir>", "-saveslice", "<out_dir>/Slices",
       "-onlymk:1"]
```

### Compute forces on an obstacle (mkbound=3)
```
tool_name: computeforces
args: ["-dirin", "<data_dir>", "-onlymk:13",
       "-savecsv", "<out_dir>/Forces"]
```
Note: ComputeForces uses absolute mk (mkbound + 11), so mkbound=3 → mk=14
for single-phase. Check the simulation XML for exact mk values.

### Measure velocity/pressure at probe points
```
tool_name: measuretool
args: ["-dirin", "<data_dir>", "-points", "<points_file>",
       "-onlytype:-all,+fluid", "-vars:+vel,+press,+rhop",
       "-savecsv", "<out_dir>/Probes"]
```

### Export specific timestep range
Add `-first:<N>` and `-last:<N>` to any tool's args to limit which
output files are processed.

## Analysis with Python

Use `run_analysis(python_code, work_dir)` to execute Python scripts that:
- Parse CSV files (numpy, pandas)
- Compute derived quantities (max run-out, flow front velocity, etc.)
- Generate plots (matplotlib)
- Save results as CSV or images

The script runs with `work_dir` as cwd. Save all output files there.

### Example: run-out distance over time
```python
import glob, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Read PartFluid CSVs (one per timestep)
files = sorted(glob.glob("particles/PartFluid_*.csv"))
times, max_x = [], []
for f in files:
    data = np.genfromtxt(f, delimiter=";", skip_header=1)
    if data.ndim == 1:
        data = data.reshape(1, -1)
    # Columns: Idp;Pos.x;Pos.y;Pos.z;Vel.x;Vel.y;Vel.z;Rhop;Press
    max_x.append(data[:, 1].max())
    # Extract timestep from filename
    idx = int(f.split("_")[-1].split(".")[0])
    times.append(idx * TIME_OUT)  # TIME_OUT from simulation params

plt.figure()
plt.plot(times, max_x, "b-o")
plt.xlabel("Time (s)")
plt.ylabel("Max run-out distance (m)")
plt.title("Debris Flow Run-out Distance")
plt.grid(True)
plt.savefig("runout_distance.png", dpi=150)
print(f"Max run-out: {max(max_x):.3f} m at t={times[max_x.index(max(max_x))]:.2f} s")
```

## Reasoning Guidelines

When the user asks an analysis question:

1. **Identify what data is needed** — particle positions? velocities? forces? surface shape?
2. **Choose the right tool**:
   - Particle positions/velocities → PartVTK with `-savecsv`
   - Surface shape → IsoSurface
   - Forces on objects → ComputeForces
   - Flow rates → FlowTool
   - Point measurements → MeasureTool
3. **Choose the right output format**:
   - For visualization → `-savevtk` (open in ParaView)
   - For analysis → `-savecsv` (parse with Python)
4. **Filter appropriately**:
   - `-onlytype:-all,+fluid` for fluid-only
   - `-onlymk:<N>` for specific material groups
   - `-onlypos:xmin:ymin:zmin:xmax:ymax:zmax` for spatial filtering
5. **Post-process with Python** if the user wants derived quantities (max distance, averages, plots)

## Available Resources

Use `read_skill_resource` to load detailed help for specific tools:

| Resource | Content |
|---|---|
| `partvtk-help.md` | Full PartVTK CLI reference (particle export, filtering, variables) |
| `isosurface-help.md` | Full IsoSurface CLI reference (surface reconstruction, slicing) |
| `other-tools-help.md` | ComputeForces, FlowTool, BoundaryVTK, FloatingInfo, PartVTKOut, MeasureTool help |
