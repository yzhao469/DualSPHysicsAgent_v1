# Drawing Shapes — Complete Command Reference

All shape-creation commands for GenCase geometry.
Based on the DualSPHysics XML Guide v5.0 §2.4.2.

---

## Boxes — `drawbox`

The most common drawing command. Defines a rectangular region.

```xml
<drawbox>
  <boxfill>solid</boxfill>
  <point x="X0" y="Y0" z="Z0" />
  <size x="SX" y="SY" z="SZ" />
</drawbox>
```

Alternative: use `<endpoint>` instead of `<size>`:
```xml
<drawbox>
  <boxfill>all</boxfill>
  <point x="0" y="0" z="0" />
  <endpoint x="4" y="2" z="1.5" />
</drawbox>
```

### boxfill values
Combine with `|`, negate with `^`:

| Value | Effect |
|-------|--------|
| `solid` | Fill entire volume |
| `all` | All 6 faces (hollow shell) |
| `top` / `bottom` | Z+ / Z− face |
| `left` / `right` | X− / X+ face |
| `front` / `back` | Y− / Y+ face |
| `all^top` | All faces except top (open-top container) |
| `bottom \| left \| right` | Only those faces |
| `bottom \| left \| right \| front \| back` | Open-top tank |

Face orientation:
```
            back (Y+)
     top ──────────── (Z+)
left │              │ right
(X−) │   bottom     │ (X+)
     │   (Z−)       │
     front ──────── (Y−)
```

**Example — open-top tank (5 faces):**
```xml
<setmkbound mk="0" />
<drawbox>
  <boxfill>bottom | left | right | front | back</boxfill>
  <point x="0" y="0" z="0" />
  <size x="1.6" y="0.67" z="0.4" />
</drawbox>
```

**Example — closed tank (all 6 faces):**
```xml
<drawbox>
  <boxfill>all</boxfill>
  <point x="0" y="0" z="0" />
  <size x="1" y="1" z="0.5" />
</drawbox>
```

---

## Rounded Shapes

### drawsphere
```xml
<drawsphere radius="0.8">
  <point x="CX" y="CY" z="CZ" />
</drawsphere>
```

When using `drawmode=face`, optional parameters control resolution:
- `ctesphere` — width of the sphere shell
- `ctespherenumsides` — number of triangles for VTK polygon output

### drawellipsoid
Two center points and a radius define the ellipsoid shape:
```xml
<drawellipsoid radius="1.8">
  <point x="1" y="0" z="0" />
  <point x="1" y="1" z="1" />
</drawellipsoid>
```

When using `drawmode=face`, `cteellipsoid` controls shell width.

### drawcylinder
Two end-points define the axis; `radius` gives the cross-section size.
```xml
<drawcylinder radius="R" mask="0">
  <point x="X1" y="Y1" z="Z1" />
  <point x="X2" y="Y2" z="Z2" />
</drawcylinder>
```

`mask` hides covers/tube surface (see Mask System below).

When using `drawmode=face`, optional parameters:
```xml
<setdpetes ctecylindertube="0.6" />
<setdpetes ctecylindercover="0.7" />
<setdpetes ctecylindernumsides="40" />
```

All three rounded shapes support `<layers vdp="..." />` for multi-layer creation.

---

## Polyhedrons

### drawpyramid
Top point + base polygon (minimum 3 base points):
```xml
<drawpyramid mask="0">
  <point x="0.25" y="0.25" z="0.7" />  <!-- apex -->
  <point x="0" y="0" z="0" />           <!-- base vertex 1 -->
  <point x="1" y="0" z="0" />           <!-- base vertex 2 -->
  <point x="0" y="1" z="0" />           <!-- base vertex 3 -->
</drawpyramid>
```

### drawprism
First half of points = base polygon, second half = top polygon.
Must have an even number of points (minimum 6).

**Basic prism (triangular cross-section):**
```xml
<drawprism mask="0">
  <point x="0" y="0" z="0" />     <!-- base 1 -->
  <point x="1" y="0" z="0" />     <!-- base 2 -->
  <point x="0" y="1" z="0" />     <!-- base 3 -->
  <point x="0" y="0" z="0.5" />   <!-- top 1 -->
  <point x="1" y="0" z="0.5" />   <!-- top 2 -->
  <point x="0" y="1" z="0.5" />   <!-- top 3 -->
</drawprism>
```

**Prism with different base and top shapes:**
```xml
<drawprism mask="0">
  <point x="0" y="0" z="0" />
  <point x="4" y="0" z="0" />
  <point x="4" y="4" z="0" />
  <point x="0" y="4" z="0" />
  <point x="2" y="1" z="5" />
  <point x="3" y="2" z="5" />
  <point x="2" y="3" z="5" />
  <point x="1" y="2" z="5" />
</drawprism>
```

**3D wave tank with sloped bottom (10-point prism):**
```xml
<drawprism mask="1 | 2 | 6 | 7">
  <point x="5" y="0" z="1.5" />
  <point x="5" y="0" z="1.1" />
  <point x="1" y="0" z="0" />
  <point x="0" y="0" z="0" />
  <point x="0" y="0" z="1.5" />
  <point x="5" y="2" z="1.5" />
  <point x="5" y="2" z="1.1" />
  <point x="1" y="2" z="0" />
  <point x="0" y="2" z="0" />
  <point x="0" y="2" z="1.5" />
</drawprism>
```

**2D beach slope (8-point prism):**
```xml
<drawprism mask="1 | 2 | 6 | 7">
  <point x="19"   y="-1" z="1.0" />
  <point x="9"    y="-1" z="0" />
  <point x="-0.5" y="-1" z="0" />
  <point x="-0.5" y="-1" z="0" />
  <point x="19"   y="1"  z="1.0" />
  <point x="9"    y="1"  z="0" />
  <point x="-0.5" y="1"  z="0" />
  <point x="-0.5" y="1"  z="0" />
</drawprism>
```

### Mask System

`mask` indicates which faces to hide. Two systems are available:

**Index-based (easier — use `|` separator):**
- `mask="1 | 2 | 6 | 7"` — hide faces 1, 2, 6, and 7; only create the rest
- Use `"X|X"` to specify a single face (avoids ambiguity with bit mode)

**Bit-based (original):**

| mask | Binary | Effect |
|------|--------|--------|
| `0` | `0000` | No faces hidden (all drawn) |
| `1` | `0001` | Face 1 hidden |
| `2` | `0010` | Face 2 hidden |
| `4` | `0100` | Face 3 hidden |
| `12` | `1100` | Faces 3 and 4 hidden |

For prisms: face 1 = base, face 2 = top, remaining = sides in vertex order.

### drawbeach
A polygon cross-section profile, extruded symmetrically. Ideal for complex bottom profiles.

```xml
<drawbeach mask="0">
  <point x="X1" y="Y1" z="Z1" />
  <point x="X2" y="Y2" z="Z2" />
  <!-- more profile points ... -->
</drawbeach>
```

The y-value of points controls the extrusion half-width (for 2D cases, use the full y span).
Points trace the cross-section outline in the XZ plane.

**Simple slope:**
```xml
<drawbeach mask="1|2|5">
  <point x="0" y="2" z="1" />
  <point x="1.5" y="2" z="0" />
  <point x="4.35" y="2" z="0" />
</drawbeach>
```

**Complex multi-segment profile:**
```xml
<drawbeach mask="1|2">
  <point x="-0.01" y="1" z="0.3" />
  <point x="0"     y="1" z="0.3" />
  <point x="0"     y="1" z="0" />
  <point x="0.45"  y="1" z="0" />
  <point x="0.45"  y="1" z="0.02" />
  <point x="0.48"  y="1" z="0.02" />
  <point x="0.48"  y="1" z="0" />
  <point x="0.8"   y="1" z="0" />
  <point x="0.8"   y="1" z="-0.01" />
  <point x="-0.01" y="1" z="-0.01" />
</drawbeach>
```

**Flat + slope transition:**
```xml
<drawbeach mask="1|2|6">
  <point x="-0.2" y="2" z="0" />
  <point x="8"    y="2" z="0" />
  <point x="10"   y="2" z="0.4" />
  <point x="10"   y="2" z="0.45" />
</drawbeach>
```

### drawextrude
Define a polygon cross-section and extrude along a vector.

```xml
<drawextrude closed="false">
  <point x="0" y="0" z="1.2" />
  <point x="0" y="0" z="0" />
  <point x="1.7" y="0" z="0" />
  <point x="3.5" y="0" z="0.5" />
  <point x="5.5" y="0" z="0.5" />
  <point x="5.5" y="0" z="1.2" />
  <extrude x="0" y="3" z="0" />
  <layers vdp="-1*,0,1*" />
</drawextrude>
```

### drawfigure
Solid figure from an indexed triangle mesh.

```xml
<drawfigure>
  <points>
    <point x="0" y="0" z="0" />
    <point x="1" y="0" z="0" />
    <point x="1" y="1" z="0" />
    <point x="0" y="1" z="0" />
    <point x="0" y="0" z="0.8" />
    <point x="1" y="0" z="0.8" />
    <point x="1" y="1" z="0.8" />
    <point x="0" y="1" z="0.8" />
  </points>
  <triangles>
    <triangle v="0" v1="1" v2="5" />
    <triangle v="1" v1="2" v2="6" />
    <triangle v="2" v1="3" v2="7" />
    <triangle v="3" v1="0" v2="4" />
    <triangle v="0" v1="2" v2="1" />
    <triangle v="4" v1="5" v2="6" />
  </triangles>
</drawfigure>
```

---

## Lines

| Command | Description |
|---------|-------------|
| `<setlinebegin>` | Sets the starting point for `<drawlineto>` |
| `<drawlineto>` | Draws a line from the last point to a new point |
| `<drawline>` | Draws a line between two explicit points |
| `<drawlines>` | Draws a connected series of lines |

```xml
<setlinebegin>
  <point x="0" y="0" z="0" />
</setlinebegin>
<drawlineto>
  <point x="0" y="1" z="0" />
</drawlineto>

<drawline>
  <point x="0" y="1" z="0" />
  <point x="1" y="1" z="0" />
</drawline>

<drawlines>
  <point x="1" y="0" z="0" />
  <point x="0" y="0" z="0.5" />
  <point x="0" y="1" z="0.5" />
  <point x="1" y="1" z="0.5" />
  <point x="1" y="0" z="0.5" />
</drawlines>
```

---

## Triangles & Polygons

### drawtriangle
Single triangle (points must go counterclockwise):
```xml
<drawtriangle>
  <point x="0" y="0" z="0" />
  <point x="1" y="0" z="0" />
  <point x="0" y="0.5" z="0" />
</drawtriangle>
```

### drawquadri
Quadrilateral from 4 points (may not be coplanar):
```xml
<drawquadri>
  <point x="0" y="0" z="0" />
  <point x="1" y="0" z="0" />
  <point x="1" y="0.5" z="0.2" />
  <point x="0" y="0.5" z="0" />
</drawquadri>
```

### drawtrianglesstrip
Chained triangles sharing edges:
```xml
<drawtrianglesstrip>
  <point x="0" y="1" z="0" />
  <point x="0" y="0" z="0" />
  <point x="1" y="1" z="0" />
  <point x="1" y="0" z="0" />
  <point x="2" y="1" z="0" />
  <point x="2" y="0" z="0" />
</drawtrianglesstrip>
```

### drawtrianglesfan
Fan of triangles radiating from the first point:
```xml
<drawtrianglesfan>
  <point x="0" y="0" z="1" />     <!-- center/apex -->
  <point x="1" y="0" z="0" />
  <point x="0.8" y="0.6" z="0" />
  <point x="0.2" y="1" z="0" />
  <point x="-0.5" y="0.9" z="0" />
</drawtrianglesfan>
```

### drawtriangles
Indexed triangle mesh (same as drawfigure points/triangles structure):
```xml
<drawtriangles>
  <points>
    <point x="0" y="0" z="0" />
    <point x="1" y="0" z="0" />
    <point x="1" y="1" z="0" />
    <point x="0" y="1" z="0" />
    <!-- ... -->
  </points>
  <triangles>
    <triangle v="0" v1="1" v2="5" />
    <!-- ... -->
  </triangles>
</drawtriangles>
```

### drawpolygon
Arbitrary polygon from a series of points:
```xml
<drawpolygon>
  <point x="0" y="0" z="0" />
  <point x="1" y="0" z="0" />
  <point x="1" y="1" z="0" />
  <point x="0" y="1" z="0" />
</drawpolygon>
```

---

## External Geometries

Import mesh files for complex shapes (terrain, hulls, turbines, obstacles).

| Command | Description |
|---------|-------------|
| `<drawfilestl>` | Load an STL file |
| `<drawfilevtk>` | Load a VTK file |
| `<drawfileply>` | Load a PLY file |
| `<drawfilecsv>` | Load a CSV file (e.g., bathymetry) |

Sub-commands for transforming imported geometry:

| Sub-command | Description |
|-------------|-------------|
| `<drawmove>` | Displacement applied to the external object |
| `<drawrotate>` | Rotation applied to the external object |
| `<drawscale>` | Scaling applied to the external object |

```xml
<drawfilestl file="mesh.stl">
  <drawscale x="1" y="1" z="1" />
  <drawmove x="2.0" y="0" z="0" />
  <drawrotate angx="0" angy="0" angz="-90" />
</drawfilestl>

<drawfilevtk file="hull.vtk">
  <drawmove x="0.75" y="0" z="0.13" />
</drawfilevtk>

<drawfileply file="object.ply" />

<drawfilecsv file="Bathymetry.csv" mode="bathymetry" />
```

VTK files support polygon selection:
```xml
<drawfilevtk file="File.vtk">
  <polyselec>triangles</polyselec>
</drawfilevtk>

<drawfilevtk file="File.vtk">
  <polyselec>points | lines</polyselec>
</drawfilevtk>
```

`autofill="true"` can automatically fill the interior of imported geometry.
