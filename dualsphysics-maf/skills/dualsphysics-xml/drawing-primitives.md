# Drawing Primitives, Fill Operations & Drawing Settings

Complete reference for GenCase drawing commands. Based on the DualSPHysics XML Guide v5.0
§2.4.2 and the official CaseTemplate.xml.

---

## Drawing Settings

Configure these at the start of `<mainlist>` before any drawing commands.

### setdrawmode — how particles are created from shapes
```xml
<setdrawmode mode="full" />
```
| Mode | Effect |
|------|--------|
| `full` | Surface + interior (most common — use by default) |
| `solid` | Interior only |
| `face` | Surface particles only (hollow shell) |
| `wire` | Edges only (wireframe) |

### setshapemode — VTK output for visualization
```xml
<setshapemode>dp | bound</setshapemode>
```
Combine with `|`: `actual`, `dp`, `bound`, `fluid`, `void`, `null`

### Other settings
```xml
<resetdraw />              <!-- Reset all options, delete all drawn points -->
<shapeout file="" />       <!-- Write VTK output (empty = default name) -->
<shapeout file="" reset="true" />  <!-- Write VTK, then clear for next group -->
<setactive drawpoints="true" drawshapes="true" vtkout="true" />
```

---

## Boxes — `drawbox`

The most common drawing command. Defines a rectangular region by corner point + size.

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

Face orientation diagram:
```
            back (Y+)
     top ──────────── (Z+)
left │              │ right
(X−) │   bottom     │ (X+)
     │   (Z−)       │
     front ──────── (Y−)
```

### Layers — create concentric shells automatically
```xml
<drawbox>
  <boxfill>bottom | left | right | front | back</boxfill>
  <point x="0" y="0" z="0" />
  <size x="4" y="2" z="1.5" />
  <layers vdp="1,-1*,3*" />
</drawbox>
```
- `vdp="0,-1"` — two layers: original and shifted inward by 1×dp
- `*` suffix means the layer is saved by `<shapeout>`

---

## Rounded Shapes

### drawsphere
```xml
<drawsphere radius="0.5">
  <point x="CX" y="CY" z="CZ" />
</drawsphere>
```

### drawellipsoid
```xml
<drawellipsoid radius="1.5">
  <point x="X1" y="Y1" z="Z1" />
  <point x="X2" y="Y2" z="Z2" />
</drawellipsoid>
```

### drawcylinder
```xml
<drawcylinder radius="R" mask="0">
  <point x="X1" y="Y1" z="Z1" />
  <point x="X2" y="Y2" z="Z2" />
</drawcylinder>
```
Axis = line between the two points. `mask` hides covers/tube surface.
All three support `<layers vdp="..." />`.

---

## Polyhedrons

### drawpyramid
```xml
<drawpyramid mask="0">
  <point x="0.25" y="0.25" z="0.7" />  <!-- apex -->
  <point x="0" y="0" z="0" />           <!-- base vertices (min 3) -->
  <point x="1" y="0" z="0" />
  <point x="0" y="1" z="0" />
</drawpyramid>
```

### drawprism
```xml
<drawprism mask="0">
  <!-- First half = base polygon, second half = top polygon -->
  <point x="X1" y="Y1" z="Z1" />  <!-- base vertex 1 -->
  <point x="X2" y="Y2" z="Z2" />  <!-- base vertex 2 -->
  <point x="X3" y="Y3" z="Z3" />  <!-- base vertex 3 -->
  <point x="X4" y="Y4" z="Z4" />  <!-- top vertex 1 -->
  <point x="X5" y="Y5" z="Z5" />  <!-- top vertex 2 -->
  <point x="X6" y="Y6" z="Z6" />  <!-- top vertex 3 -->
</drawprism>
```

**Rules:**
- Must have an even number of points (minimum 6)
- First half = base polygon, second half = matching top polygon
- The two polygons are connected face-to-face
- Common configurations: 6 points (2 triangles), 8 points (2 quads), 10 points (2 pentagons)

**Example — 3D wave tank with sloped bottom (10-point prism):**
```xml
<!-- From CaseWavemaker_Def.xml -->
<drawprism mask="0">
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

**Example — 2D beach slope (8-point prism):**
```xml
<!-- From CasePistonBeach_REG_Def.xml -->
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

**Example — simple slope (from CaseBowling_Def.xml):**
```xml
<drawbeach mask="1|2|5">
  <point x="0" y="2" z="1" />
  <point x="1.5" y="2" z="0" />
  <point x="4.35" y="2" z="0" />
</drawbeach>
```

**Example — complex multi-segment profile (from CasePeriodicity_Def.xml):**
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

**Example — flat + slope transition (from CaseWaves2D_Def.xml):**
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
  <point x="1.7" y="1" z="0" />
  <point x="3.5" y="1" z="0.5" />
  <extrude x="0" y="3" z="0" />
  <layers vdp="-1*,0,1*" />
</drawextrude>
```

### drawfigure
Solid figure from triangles (indexed triangle mesh).

```xml
<drawfigure>
  <points>
    <point x="0" y="0" z="0" />
    <point x="1" y="0" z="0" />
    <!-- ... -->
  </points>
  <triangles>
    <triangle x="0" y="1" z="5" />  <!-- vertex indices -->
    <!-- ... -->
  </triangles>
</drawfigure>
```

### Mask parameter (pyramid, prism, beach, extrude, cylinder)

**Index-based system (easier — use `|` separator):**
- `mask="1 | 2 | 6 | 7"` — only create faces 1, 2, 6, and 7
- Use `"X|X"` for a single face (avoids ambiguity with bit mode)

**Bit-based system (original):**
- `mask="0"` — all faces drawn (no faces hidden)
- `mask="1"` (binary 0001) — hide face 1
- `mask="12"` (binary 1100) — hide faces 3 and 4

For prisms: face 1 = base, face 2 = top, remaining faces = sides in vertex order.

---

## Lines & Triangles

Typically used for thin boundaries, terrain surfaces, or custom shapes.

### Lines
```xml
<drawline>
  <point x="0" y="0" z="0" />
  <point x="1" y="0" z="1" />
</drawline>
<drawlines>   <!-- connected series of lines -->
  <point ... /> <point ... /> <point ... />
</drawlines>
```

### Triangles
```xml
<drawtriangle>  <!-- single triangle, points counterclockwise -->
  <point ... /> <point ... /> <point ... />
</drawtriangle>

<drawquadri>    <!-- quadrilateral (4 points) -->
  <point ... /> <point ... /> <point ... /> <point ... />
</drawquadri>

<drawtrianglesstrip>  <!-- chained triangles sharing edges -->
  <point ... /> <point ... /> ...
</drawtrianglesstrip>

<drawtrianglesfan>    <!-- fan of triangles from first point -->
  <point ... /> <point ... /> ...
</drawtrianglesfan>

<drawtriangles>       <!-- indexed triangle mesh -->
  <points> <point ... /> ... </points>
  <triangles> <triangle x="0" y="1" z="2" /> ... </triangles>
</drawtriangles>

<drawpolygon>         <!-- arbitrary polygon -->
  <point ... /> <point ... /> ...
</drawpolygon>
```

---

## External Geometries

Import mesh files for complex shapes (terrain, hulls, turbines, obstacles).

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

- `drawscale`, `drawmove`, `drawrotate` transform the imported geometry
- `autofill="true"` — automatically fill the interior
- VTK files support `<polyselec>` to choose which polygon types to import

---

## Fill Operations

Flood-fill a region with particles. Essential for placing fluid inside complex
boundary geometries or on top of irregular surfaces.

### fillbox — fill within a bounding box
```xml
<fillbox x="FX" y="FY" z="FZ">
  <modefill>void</modefill>
  <point x="X0" y="Y0" z="Z0" />
  <size x="SX" y="SY" z="SZ" />
</fillbox>
```
- **(FX, FY, FZ)** = seed point, must be inside the target void region
- Fills connected space of the given type within the box bounds
- Respects existing boundaries — fluid fills around/above them

### fillpoint — fill all connected space
```xml
<fillpoint x="FX" y="FY" z="FZ">
  <modefill>void</modefill>
</fillpoint>
```

### fillvoidpoint — shorthand for void fill
```xml
<fillvoidpoint x="FX" y="FY" z="FZ" />
```

### fillprism / fillfigure — fill within a prism or triangle mesh
```xml
<fillprism x="FX" y="FY" z="FZ">
  <point ... /> <!-- prism vertices -->
  <modefill>void</modefill>
</fillprism>
```

### modefill modes
| Mode | Effect |
|------|--------|
| `void` | Fill empty space only (most common) |
| `fluid` | Replace existing fluid particles |
| `bound` | Replace existing boundary particles |
| `border` | Fill based on neighbouring particle type |

---

## Redraw

Reassign the MK of existing particles based on conditions.
Useful for patching gaps in complex boundary geometries before filling.

```xml
<!-- Change all nodes with mk to current mk setting -->
<redraw mkfluid="0" />

<!-- Change fluid nodes that neighbour boundary nodes -->
<redrawnear targettp="fluid" bordertp="bound" />

<!-- Same, but restricted to a box region -->
<redrawnearbox targettp="void" bordertp="bound" bordermk="2">
  <point x="0" y="0" z="0" />
  <size x="4" y="2" z="1" />
</redrawnearbox>
```

---

## FreeDraw Mode

Place particles at free positions (not on the cubic lattice) while maintaining dp spacing.

```xml
<setfrdrawmode auto="true" />
<!-- drawing commands use free positioning -->
<setfrdrawmode auto="false" />
```
