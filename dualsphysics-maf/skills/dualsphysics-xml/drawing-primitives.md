# Drawing Primitives & Fill Operations

## C. Drawing Primitives

### drawbox
```xml
<drawbox>
  <boxfill>solid</boxfill>
  <point x="X0" y="Y0" z="Z0" />
  <size x="SX" y="SY" z="SZ" />
</drawbox>
```
`<point>` is the min corner (origin). `<size>` gives extent in each axis.

**boxfill grammar** (can combine with `|`):
- `solid` — fill the entire box
- `top`, `bottom`, `left`, `right`, `front`, `back` — only the named face(s)
- `all` — all six faces (hollow box shell)
- Example: `<boxfill>bottom | left | right</boxfill>` draws floor + two walls

### drawcylinder
```xml
<drawcylinder radius="R">
  <point x="X1" y="Y1" z="Z1" />
  <point x="X2" y="Y2" z="Z2" />
</drawcylinder>
```
Cylinder from point1 to point2 with given radius. Axis is the line between the two points.

### drawsphere
```xml
<drawsphere radius="R">
  <point x="CX" y="CY" z="CZ" />
</drawsphere>
```

### drawellipsoid
```xml
<drawellipsoid>
  <point x="CX" y="CY" z="CZ" />
  <size x="RX" y="RY" z="RZ" />
</drawellipsoid>
```
Semi-axes are `RX`, `RY`, `RZ` from centre.

### drawprism
```xml
<drawprism mask="0">
  <point x="X1" y="Y1" z="Z1" />
  <point x="X2" y="Y2" z="Z2" />
  <point x="X3" y="Y3" z="Z3" />
  <point x="X4" y="Y4" z="Z4" />
  <!-- 3-8 points defining a polygon, extruded in y -->
</drawprism>
```
Defines a polygon in the XZ plane (or any plane), extruded along y. Use `mask` to control which faces are drawn (0=all, 1-6=specific faces).

### drawextrude
```xml
<drawextrude>
  <point x="X1" y="Y1" z="Z1" />
  <point x="X2" y="Y2" z="Z2" />
  <!-- ... polygon vertices ... -->
  <extrude x="EX" y="EY" z="EZ" />
</drawextrude>
```
Extrudes a polygon along the given vector.

### drawbeach
```xml
<drawbeach>
  <point x="X0" y="Y0" z="Z0" />
  <size x="SX" y="SY" z="SZ" />
  <angle value="A" />
</drawbeach>
```
Creates a sloped surface (beach/ramp). Angle `A` in degrees.

### drawpyramid
```xml
<drawpyramid>
  <point x="X1" y="Y1" z="Z1" />
  <point x="X2" y="Y2" z="Z2" />
  <point x="X3" y="Y3" z="Z3" />
  <point x="X4" y="Y4" z="Z4" />
  <point x="X5" y="Y5" z="Z5" />  <!-- apex -->
</drawpyramid>
```

### drawfilestl / drawfilevtk / drawfileply
```xml
<drawfilestl file="path/to/mesh.stl" objname="">
  <drawscale x="1" y="1" z="1" />
  <drawmove x="0" y="0" z="0" />
  <drawrotate angx="0" angy="0" angz="0" />
</drawfilestl>
```
Import external mesh geometry. Useful for complex shapes (ship hulls, turbines, terrain).
- `file`: path to the STL/VTK/PLY file (relative to XML or absolute)
- `drawscale`, `drawmove`, `drawrotate`: apply transforms before placing

---

## D. Fill Operations

Fill operations fill a region with fluid particles.

### fillbox
```xml
<fillbox x="FX" y="FY" z="FZ">
  <modefill>void</modefill>
  <point x="X0" y="Y0" z="Z0" />
  <size x="SX" y="SY" z="SZ" />
</fillbox>
```
- Seed point `(FX, FY, FZ)` must be inside the region
- `<modefill>void</modefill>` = fill where there are currently void/empty particles
- Only fills connected empty space reachable from the seed (flood-fill)

### fillpoint
```xml
<fillpoint x="FX" y="FY" z="FZ">
  <modefill>void</modefill>
</fillpoint>
```
Flood-fill from a single seed point (fills all connected void).

### modefill modes
- `void` — fill empty space only
- `fluid` — replace existing fluid
- `bound` — replace existing boundary
