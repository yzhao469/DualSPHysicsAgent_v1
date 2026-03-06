# IsoSurface — Full CLI Reference

Reconstructs free surface mesh from particle data or computes planar slices.

```
IsoSurface <options>

Define input file:
  -dirin <dir>       Directory with particle data
  -casein <casename> Name of case file with particle data
  -filexml file.xml  Loads xml file with mk info. Use 'AUTO' for simulation xml.
  -first:<int>       First file to process
  -last:<int>        Last file to process
  -files:<values>    Number of files to process
  -move:x:y:z        Offset particles

Input data filters:
  -onlypos:xmin:ymin:zmin:xmax:ymax:zmax  Spatial limits
  -onlyposfile filters.xml                 XML filter file
  -onlymk:<values>                         Filter by mk value
  -onlytype:<values>                       Filter by type:
     +/-all, +/-bound, +/-fixed, +/-moving, +/-floating, +/-fluid
     (Default: fluid)

Variables:
  -vars:<values>  Variables to compute:
     +/-all, +/-idp, +/-vel, +/-rhop, +/-press, +/-mass,
     +/-vol, +/-type, +/-mk, +/-ace, +/-vor
     (Default: vel)

Parameters for acceleration/vorticity:
  -viscoart:<float>    Artificial viscosity [0-1]
  -viscolam:<float>    Laminar viscosity [~1E-6]
  -gravity:<float:float:float>  Gravity vector

Interpolation configuration:
  -distinter_2h:<float>  Max interaction distance as coefficient of 2h (default 1.0)
  -distinter:<float>     Max interaction distance (absolute)
  -kclimit:<float>       Min sum_wab_vol for Kernel Correction (default 0.05)
  -kcdummy:<float>       Dummy value when KC not applied (default 0)
  -kcusedummy:<0/1>      Whether to use dummy value (default 1)

Isosurface configuration:
  -iso_limits:xmin:ymin:zmin:xmax:ymax:zmax  Adjust isosurface limits
  -distnode_dp:<float>   Node distance as multiple of dp (default)
  -distnode:<float>      Absolute node distance

Output files:
  -saveiso <file.vtk>    VTK polydata with isosurface (mass-based, threshold
                         = 0.5 * fluid particle mass by default)
  -isovar:var:<values>   Isosurface from a specific variable with given limits
  -saveslice <file.vtk>  VTK polydata with planar slice of isosurface
  -slicevec:ptx:pty:ptz:vecx:vecy:vecz   Slice plane from point + normal vector
  -slice3pt:pt1x:pt1y:pt1z:pt2x:pt2y:pt2z:pt3x:pt3y:pt3z  Slice from 3 points
  -slicedata:<mode>      How to handle data at vertices:
     none, nearest, interpolate (default)
  -createdirs:<0/1>      Create output directories (default 1)

Examples:
  IsoSurface -dirin data/ -saveiso surface.vtk
  IsoSurface -dirin data/ -saveslice slices.vtk -onlymk:1
  IsoSurface -dirin data/ -saveiso surface.vtk -isovar:mass:3.2,3.1,3.0
```

## Notes
- For 2D simulations, slice configuration is automatic
- `-saveslice` is useful for 2D cross-section views of 3D simulations
- Use `-onlymk` to reconstruct surface of a specific fluid phase
