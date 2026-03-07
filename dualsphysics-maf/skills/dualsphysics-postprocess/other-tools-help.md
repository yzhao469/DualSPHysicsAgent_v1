# Other Post-Processing Tools

## ComputeForces

Computes forces and moments on boundary particles.

```
ComputeForces <options>

Input:
  -dirin <dir>       Directory with particle data
  -filexml file.xml  XML with mk info (use 'AUTO')
  -first:<int>       First file
  -last:<int>        Last file

Force calculation parameters:
  -viscoart:<float>      Artificial viscosity [0-1] (default 0)
  -viscolam:<float>      Laminar viscosity [~1E-6]
  -viscoauto:            Load viscosity config from BI4 files
  -gravity:<float:float:float>  Gravity value

Moment calculation:
  -momentaxis:x1:y1:z1:x2:y2:z2  Axis for moment calculation

Filters:
  -onlypos:xmin:ymin:zmin:xmax:ymax:zmax  Spatial limits
  -onlymk:<values>     Filter by mk (use absolute mk: mkbound + 11)
  -onlyid:<values>     Filter by particle id

Output:
  -savecsv <file.csv>    CSV with force time history
  -saveascii <file.asc>  ASCII without headers
  -savevtk <file.vtk>    VTK with selected particles

Example:
  ComputeForces -dirin data/ -onlymk:14 -savecsv forces
```

---

## FlowTool

Computes flow rates through defined box regions.

```
FlowTool <options>

Input:
  -dirin <dir>         Directory with particle data bi4
  -fileboxes <file>    File with prism domain definitions
  -first:<int>         First file
  -last:<int>          Last file

Output:
  -boxestemplate       Creates example fileboxes template
  -savecsv <file.csv>  CSV with particle count, volume, flow rates
  -savevtk <file.vtk>  VTK with particles

Example:
  FlowTool -dirin data/ -fileboxes boxes.dat -savecsv flow_results.csv
```

---

## BoundaryVTK

Generates VTK files for boundary shapes, with optional motion animation.

```
BoundaryVTK <options>

Load shapes:
  -loadvtk <file.vtk>    Load shapes from VTK (use AutoActual or AutoDp)
  -onlymk:<values>       Filter shapes by mk
  -loadstl:<mk> <file>   Load STL with given mk
  -loadply:<mk> <file>   Load PLY with given mk

Motion:
  -filexml file.xml       XML with movement info (use 'AUTO')
  -motiondata <dir>       Load particle positions for mobile boundary
  -motiondatatime <dir>   Load real times for mobile boundary
  -motiontime:<time>:<step>  Duration and step for xml-defined motion

Output:
  -savevtk <file.vtk>       VTK polydata
  -savevtkdata <file.vtk>   VTK polydata with mk and shape code
  -saveply <file.ply>        PLY format
  -savestl <file.stl>        STL format
  -savemotion <file>         CSV with object movement

Example:
  BoundaryVTK -loadvtk AutoActual -filexml AUTO -motiondata data/ -savevtkdata boundary.vtk
```

---

## FloatingInfo

Extracts motion and force data for floating bodies.

```
FloatingInfo <options>

Input:
  -dirin <dir>       Directory with particle data
  -filein <file>     Input file (PartFloat.fbi4 by default)
  -first:<int>       First file
  -last:<int>        Last file

Output:
  -savedata <file>      CSV with floating body data
  -savemotion:<0/1>     Include motion data (default 1)
  -onlymk:<values>      Filter by mk

Example:
  FloatingInfo -dirin data/ -savedata floating_results -onlymk:61
```

---

## PartVTKOut

Extracts excluded (escaped) particles.

```
PartVTKOut <options>

Input:
  -dirin <dir>       Directory with particle data
  -filexml file.xml  XML with mk info
  -first:<int>       First file
  -last:<int>        Last file

Output:
  -savevtk <file.vtk>     VTK with excluded particles
  -savecsv <file.csv>     CSV with particle info
  -SaveResume <file.csv>  CSV with resume/summary info

Filters:
  -onlypos:xmin:ymin:zmin:xmax:ymax:zmax  Spatial limits
  -onlynew              Only new excluded particles per PART file
  -limitpos:xmin:ymin:zmin:xmax:ymax:zmax  Change simulation limits
  -limitrhop:min:max    Change rhop limits

Example:
  PartVTKOut -dirin data/ -savevtk excluded.vtk -SaveResume resume.csv
```

---

## MeasureTool

Interpolates field values at specified probe points.

```
MeasureTool <options>

Input:
  -dirin <dir>       Directory with particle data
  -filexml file.xml  XML with mk info (use 'AUTO')
  -first:<int>       First file
  -last:<int>        Last file

Probe points:
  -points <file>           Points file (POINTSLIST format)
  -pointspos <file>        Position-based points
  -particlesmk:<values>    Use particle positions as probe points
  -pointstemplate          Create example points file

Particle filters:
  -onlytype:<values>   +/-all, +/-bound, +/-fluid, etc.
  -onlymk:<values>     Filter by mk

Variables:
  -vars:<values>   +/-vel, +/-rhop, +/-press, +/-mass, +/-ace, +/-vor, etc.
  -elevation[:<float>]  Compute fluid elevation
  -tke                  Turbulent Kinetic Energy

Output:
  -savevtk <file.vtk>    VTK with interpolation points
  -savecsv <file.csv>    CSV with time history
  -saveascii <file.asc>  ASCII without headers

Example:
  MeasureTool -dirin data/ -points probes.txt -onlytype:-all,+fluid -vars:+vel,+press -savecsv results
```
