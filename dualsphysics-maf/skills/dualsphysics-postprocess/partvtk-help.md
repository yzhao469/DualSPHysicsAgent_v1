# PartVTK — Full CLI Reference

Extracts particles from simulation binary data and exports as VTK or CSV.

```
PartVTK <options>

Define input file:
  -dirin <dir>       Directory with particle data
  -casein <casename> Name of case file with particle data
  -filexml file.xml  Loads xml file with mk info. Use 'AUTO' for the simulation xml.
  -first:<int>       First file to process
  -last:<int>        Last file to process
  -files:<values>    Number of files to process
  -move:x:y:z        Offset all particles by this vector

Define output file:
  -savevtk <file.vtk>       VTK polydata files with particles
  -saveascii <file.asc>     ASCII files without headers
  -savecsv <file.csv>       CSV files for spreadsheets
  -savestatscsv <file.csv>  CSV files with statistics
  -createdirs:<0/1>         Create output directories (default 1)
  -csvsep:<0/1>             CSV separator: 0=semicolon, 1=comma (default 0)

Particle filters (per output file):
  -onlypos:xmin:ymin:zmin:xmax:ymax:zmax  Spatial limits
  -onlyposfile filters.xml                 XML filter file
  -onlyvel:vmin:vmax                       Velocity range
  -onlymk:<values>                         Filter by mk value
  -onlyid:<values>                         Filter by particle id
  -onlytype:<values>                       Filter by type:
     +/-all, +/-bound, +/-fixed, +/-moving, +/-floating, +/-fluid
     (+ = include, - = exclude. Default: all)

Variables (per output file):
  -vars:<values>  Variables to compute and store:
     +/-all, +/-idp, +/-vel, +/-rhop, +/-press, +/-mass,
     +/-vol, +/-type, +/-mk, +/-ace, +/-vor
     (Default: idp, vel, rhop, type)

Parameters for acceleration/vorticity:
  -viscoart:<float>    Artificial viscosity [0-1]
  -viscolam:<float>    Laminar viscosity [~1E-6]
  -gravity:<float:float:float>  Gravity vector
  -distinter_2h:<float>         Max interaction distance as coefficient of 2h (default 1.0)
  -distinter:<float>            Max interaction distance (absolute)

Examples:
  PartVTK -dirin data/ -savevtk partfluid.vtk -onlytype:-all,+fluid -vars:+vel,+rhop,+press
  PartVTK -dirin data/ -savecsv partdata.csv -onlytype:-all,+fluid -vars:+idp,+vel,+rhop
  PartVTK -dirin data/ -savevtk partbound.vtk -onlytype:-all,+bound -vars:+mk,+rhop
```

## CSV Output Format
- Semicolon-separated by default (use `-csvsep:1` for comma)
- One file per timestep: `filename_NNNN.csv`
- Header row with column names
- Columns depend on `-vars`: Idp;Pos.x;Pos.y;Pos.z;Vel.x;Vel.y;Vel.z;Rhop;Press;...
