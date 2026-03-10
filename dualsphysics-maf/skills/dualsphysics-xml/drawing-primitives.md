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
- Example: `<boxfill>bottom | left | right | front | back</boxfill>` draws open-top tank (5 faces)

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

### drawprism — IMPORTANT for slopes and inclined surfaces
```xml
<drawprism mask="0">
  <point x="X1" y="Y1" z="Z1" />
  <point x="X2" y="Y2" z="Z2" />
  <point x="X3" y="Y3" z="Z3" />
  <point x="X4" y="Y4" z="Z4" />
  <point x="X5" y="Y5" z="Z5" />
  <point x="X6" y="Y6" z="Z6" />
</drawprism>
```

**How it works:** A prism is defined by **two parallel polygons** connected face-to-face.
- Points 1–N/2 define the first polygon (e.g., at `y=-1`)
- Points N/2+1–N define the matching second polygon (e.g., at `y=1`)
- The two polygons must have the same number of vertices
- Typical usage: 6 points (2 triangles) or 8 points (2 quadrilaterals)

**mask parameter:** Controls which faces are drawn.
- `mask="0"` — all faces (solid prism)
- `mask="1 | 2 | 6 | 7"` — specific faces only (use for slopes where you only want the surface)

**Creating an inclined surface (slope/ramp):**
Use a prism where the z-coordinates vary along x to create a slope:
```xml
<!-- Ramp rising from z=0 at x=0 to z=1.0 at x=5 (2D case) -->
<drawprism mask="1 | 2 | 6 | 7">
  <point x="5"    y="-1" z="1.0" />  <!-- high end -->
  <point x="0"    y="-1" z="0" />    <!-- low end -->
  <point x="-0.5" y="-1" z="0" />    <!-- extend past low end -->
  <point x="-0.5" y="-1" z="0" />    <!-- duplicate to close polygon -->
  <point x="5"    y="1"  z="1.0" />  <!-- same shape, other y-side -->
  <point x="0"    y="1"  z="0" />
  <point x="-0.5" y="1"  z="0" />
  <point x="-0.5" y="1"  z="0" />
</drawprism>
```

**Creating a flat floor + slope transition:**
```xml
<!-- Flat from x=0 to x=3, then slope up from z=0 to z=0.8 at x=5 -->
<drawprism mask="0">
  <point x="5"  y="-1" z="0.8" />
  <point x="3"  y="-1" z="0" />
  <point x="0"  y="-1" z="0" />
  <point x="0"  y="-1" z="-0.04" />
  <point x="5"  y="1"  z="0.8" />
  <point x="3"  y="1"  z="0" />
  <point x="0"  y="1"  z="0" />
  <point x="0"  y="1"  z="-0.04" />
</drawprism>
```

### drawbeach — polygon-profile slope
```xml
<drawbeach mask="1|2|6">
  <point x="X1" y="Y1" z="Z1" />
  <point x="X2" y="Y2" z="Z2" />
  <point x="X3" y="Y3" z="Z3" />
  <point x="X4" y="Y4" z="Z4" />
</drawbeach>
```

**How it works:** `drawbeach` takes a series of (x, z) profile points (all at the same y-value)
and creates a solid cross-section that is extruded symmetrically about y=0.
The y-value of the points defines the half-width of the extrusion.

**Example — flat floor transitioning to a slope:**
```xml
<drawbeach mask="1|2|6">
  <point x="-0.2" y="2" z="0" />     <!-- start of flat section -->
  <point x="8"    y="2" z="0" />     <!-- end of flat / start of slope -->
  <point x="10"   y="2" z="0.4" />   <!-- top of slope -->
  <point x="10"   y="2" z="0.45" />  <!-- thickness of slope wall -->
</drawbeach>
```
This creates: flat bottom from x=-0.2 to x=8 at z=0, then a slope rising to z=0.4 at x=10.

**Example — complex multi-segment profile:**
```xml
<drawbeach mask="1|2">
  <point x="-0.01" y="1" z="0.3" />
  <point x="0"     y="1" z="0.3" />
  <point x="0"     y="1" z="0" />     <!-- vertical drop -->
  <point x="0.45"  y="1" z="0" />     <!-- flat section -->
  <point x="0.45"  y="1" z="0.02" />  <!-- small step up -->
  <point x="0.48"  y="1" z="0.02" />
  <point x="0.48"  y="1" z="0" />     <!-- step back down -->
  <point x="0.8"   y="1" z="0" />     <!-- flat section -->
  <point x="0.8"   y="1" z="-0.01" />
  <point x="-0.01" y="1" z="-0.01" />
</drawbeach>
```

**mask parameter** for drawbeach:
- `1` = bottom face
- `2` = front/back faces
- `6` = top face
- Combine with `|`: `mask="1|2|6"` draws bottom + sides + top

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

Fill operations fill a region with fluid particles. Essential for placing fluid
on inclined surfaces or inside complex boundary shapes.

### fillbox
```xml
<fillbox x="FX" y="FY" z="FZ">
  <modefill>void</modefill>
  <point x="X0" y="Y0" z="Z0" />
  <size x="SX" y="SY" z="SZ" />
</fillbox>
```
- Seed point `(FX, FY, FZ)` must be inside the region **and above any boundary surface**
- `<modefill>void</modefill>` = fill where there are currently void/empty particles
- Only fills connected empty space reachable from the seed (flood-fill)
- The fill respects existing boundary particles — fluid will sit on top of slopes
- For 2D cases, seed point y should be 0

**Common pattern — fluid on a slope:**
```xml
<!-- 1. Draw the slope as boundary -->
<setmkbound mk="0" />
<drawprism mask="1 | 2 | 6 | 7"> ... </drawprism>
<!-- 2. Fill fluid on top of the slope -->
<setmkfluid mk="0" />
<fillbox x="0.5" y="0" z="0.05">
  <modefill>void</modefill>
  <point x="-1" y="-1" z="-1" />
  <size x="20" y="2" z="2" />
</fillbox>
```
The seed point (0.5, 0, 0.05) must be in a void region above the slope surface.
The fillbox bounds should be large enough to encompass the desired fill region.

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
