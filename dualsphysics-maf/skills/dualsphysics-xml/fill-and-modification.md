# Fill Operations, Redraw, Freedraw & Layers

Commands for placing particles in regions, modifying existing particles,
and creating multi-layer shells.
Based on the DualSPHysics XML Guide v5.0 §2.4.2.

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

### fillpoint — fill all connected space from a seed
```xml
<fillpoint x="FX" y="FY" z="FZ">
  <modefill>void</modefill>
</fillpoint>
```

Optional attributes to override the current mk:
```xml
<fillpoint x="1" y="1" z="1" mkfluid="0">
  <modefill>fluid</modefill>
</fillpoint>

<fillpoint x="1" y="1" z="1" mkbound="0">
  <modefill>bound</modefill>
</fillpoint>

<fillpoint x="2" y="2" z="2" mkfluid="2" mkbound="2">
  <modefill>border | void | fluid | bound</modefill>
</fillpoint>
```

### fillvoidpoint — shorthand for void fill
```xml
<fillvoidpoint x="FX" y="FY" z="FZ" />
```

### fillprism — fill within a prism
```xml
<fillprism x="FX" y="FY" z="FZ">
  <point x="0" y="0" z="0" />
  <point x="1" y="0" z="0" />
  <point x="0" y="1" z="0" />
  <point x="0" y="0" z="0.5" />
  <point x="1" y="0" z="0.5" />
  <point x="0" y="1" z="0.5" />
  <modefill>void</modefill>
</fillprism>
```

### fillfigure — fill within a triangle mesh
```xml
<fillfigure x="FX" y="FY" z="FZ">
  <points> ... </points>
  <triangles> ... </triangles>
  <modefill>void</modefill>
</fillfigure>
```

### modefill modes

| Mode | Effect |
|------|--------|
| `void` | Fill empty space only (most common for placing fluid) |
| `fluid` | Replace existing fluid particles |
| `bound` | Replace existing boundary particles |
| `border` | Use the presence of a given type of point as a boundary |

Modes can be combined: `<modefill>border | void | fluid | bound</modefill>`

### setboxlimitmode
Controls how fillbox interacts with the fill boundary:
```xml
<setboxlimitmode mode="full" />
```
Ensures fill extends to box edges (useful for inlet/outlet zones).

### Typical fill workflow

1. Draw boundaries first (walls, floor, obstacles)
2. Set `<setmkfluid mk="0" />`
3. Use `<fillbox>` with a seed point inside the target void region
4. The seed must be in empty space (void), not inside a boundary

**Example — fill fluid above a slope:**
```xml
<setmkfluid mk="0" />
<fillbox x="0.5" y="0" z="0.05">
  <modefill>void</modefill>
  <point x="-1" y="-1" z="-1" />
  <size x="20" y="2" z="1.66" />
</fillbox>
```

---

## Redraw Commands

Reassign the MK of existing particles based on conditions.
Useful for patching gaps in complex boundary geometries before filling.

| Command | Description |
|---------|-------------|
| `<redraw>` | Assign current mk to all nodes matching a condition |
| `<redrawnear>` | Modify nodes neighbouring a given type |
| `<redrawbox>` | Same as `<redraw>` but limited to a box region |
| `<redrawnearbox>` | Same as `<redrawnear>` but limited to a box region |

### redraw — assign mk by condition
```xml
<redraw />                <!-- All nodes to current mk -->
<redraw mkfluid="0" />    <!-- Only nodes with mkfluid=0 -->
<redraw mkbound="5" />    <!-- Only nodes with mkbound=5 -->
```

### redrawnear — modify neighbours
```xml
<!-- Change fluid nodes that neighbour boundary nodes -->
<redrawnear targettp="fluid" bordertp="bound" />

<!-- Same but run 2 iterations -->
<redrawnear times="2" targettp="fluid" bordertp="bound" />

<!-- Target specific mk values -->
<redrawnear targettp="void" bordertp="bound" bordermk="2" />
```

### redrawbox / redrawnearbox — region-limited
```xml
<redrawbox mkfluid="0">
  <point x="0.1" y="1" z="1.1" />
  <size x="3" y="4" z="2" />
</redrawbox>

<redrawnearbox times="3" targettp="void">
  <point x="0.1" y="1" z="1.1" />
  <size x="3" y="4" z="2" />
</redrawnearbox>
```

### Practical example: closing holes in imported geometry

Redraw commands can close holes in complex boundary geometries before filling with fluid:

```xml
<!-- Creates vertical piston. -->
<setmkbound mk="0" />
<drawline>
  <point x="0" y="0" z="2" />
  <point x="0" y="0" z="0" />
</drawline>
<!-- Creates bottom from external geometry. -->
<setmkbound mk="1" />
<drawfilevtk file="Bottom.vtk" />
<!-- Fills the holes with boundary particles. -->
<setmkbound mk="2" />
<redrawnear times="1" targettp="void"
  bordertp="bound" bordermk="1" />
<!-- Now fill fluid safely. -->
<setmkfluid mk="0" />
<fillbox x="0.5" y="0" z="0.5">
  <modefill>void</modefill>
  <point x="0" y="-1" z="0" />
  <size x="6" y="2" z="1.5" />
</fillbox>
```

---

## Freedraw Mode

Place particles at free positions (not on the cubic lattice) while maintaining dp spacing.
Produces better surface representation for curved geometries.

```xml
<setfrdrawmode auto="true" />
<!-- drawing commands use free positioning -->
<setfrdrawmode auto="false" />
```

**Sphere with freedraw:**
```xml
<setdrawmode mode="full" />
<setmkbound mk="0" name="Sphere" />
<setfrdrawmode auto="true" />
<drawsphere radius="5.0">
  <point x="0" y="0" z="5.0" />
</drawsphere>
<setfrdrawmode auto="false" />
```

**Cylinder with freedraw:**
```xml
<setdrawmode mode="face" />
<setmkbound mk="0" name="Cylinder" />
<setfrdrawmode auto="true" />
<drawcylinder radius="4.0" mask="0">
  <point x="0" y="0" z="0" />
  <point x="0" y="0" z="10" />
</drawcylinder>
<setfrdrawmode auto="false" />
```

---

## Layers

Create several concentric shells automatically. Supported by:
`<drawbox>`, `<drawextrude>`, `<drawsphere>`, and `<drawcylinder>`.

The `vdp` attribute specifies layer offsets in units of dp.
The asterisk `*` marks layers saved by `<shapeout>`.

```xml
<drawbox>
  <boxfill>all</boxfill>
  <point x="2" y="-1" z="1.5" />
  <size x="1.4" y="2" z="2" />
  <layers vdp="0*,-1" />
</drawbox>
```
- `vdp="0,-1"` — two layers: original position and shifted inward by 1×dp
- `vdp="0*,-1"` — same, but only the first layer is saved to VTK

**Cylinder with 4 layers:**
```xml
<drawcylinder radius="0.5" mask="2">
  <point x="7" y="-1" z="2.5" />
  <point x="7" y="1" z="2.5" />
  <layers vdp="0,1,3,4*" />
</drawcylinder>
```

**Extrude with 3 layers:**
```xml
<drawextrude closed="false">
  <point x="0" y="0" z="3" />
  <point x="2" y="0" z="0" />
  <point x="8" y="0" z="0" />
  <point x="9" y="0" z="1" />
  <point x="10" y="0" z="1" />
  <point x="10" y="0" z="2" />
  <point x="11" y="0" z="2" />
  <point x="12" y="0" z="3" />
  <extrude x="0" y="1" z="0" />
  <layers vdp="0*,-1,-2" />
</drawextrude>
```
