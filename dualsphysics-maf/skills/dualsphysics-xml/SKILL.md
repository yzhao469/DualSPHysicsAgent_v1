---
name: dualsphysics-xml
description: Comprehensive GenCase geometry DSL, physics parameters, and probe placement reference for DualSPHysics non-Newtonian simulations.
---

# DualSPHysics GenCase — Core Reference

You generate the full `<geometry>` XML block for any DualSPHysics scenario.
This skill provides the XML structure, physics parameters, material archetypes,
probe placement heuristics, and reasoning guidelines.

For detailed commands, load the resources listed at the bottom of this document.

---

## A. XML Structure

A DualSPHysics case XML has this skeleton:

```xml
<case>
  <casedef>
    <constantsdef> ... </constantsdef>
    <mkconfig boundcount="240" fluidcount="9" />
    <geometry>
      <definition dp="0.01">
        <pointmin x="-0.5" y="0" z="-0.5" />
        <pointmax x="5.0" y="0" z="5.0" />
      </definition>
      <commands>
        <mainlist>
          <!-- drawing commands go here -->
          <shapeout file="" />
        </mainlist>
      </commands>
    </geometry>
  </casedef>
  <execution>
    <special>
      <nnphases> ... </nnphases>
    </special>
    <parameters> ... </parameters>
  </execution>
</case>
```

**Key rules:**
- `dp` = inter-particle distance (m). Controls resolution. Halving dp → ~8× particles, ~8× runtime.
- `<pointmin>` / `<pointmax>` define the domain bounding box. Must enclose all geometry with margin (~0.5–1.0 m).
- `<mainlist>` is executed top-to-bottom. Order matters — later commands overwrite earlier particles.
- Always end `<mainlist>` with `<shapeout file="" />` to write VTK output.

---

## B. Domain Limits

`dp` defines the distance between particles. Particles are only created within the domain defined by `pointmin` and `pointmax`.

```xml
<definition dp="0.005">
  <pointmin x="-0.05" y="0.1" z="-0.05" />
  <pointmax x=" 2.00" y="0.1" z=" 1.00" />
</definition>
```

Variables can parametrise dp and domain limits using `<predefinition>` (see transforms-and-variables.md).

---

## C. 2D vs 3D — CRITICAL

### 2D simulation
**`pointmin y` and `pointmax y` MUST be equal** to tell GenCase this is 2D.
Typically both are set to `y=0`:

```xml
<definition dp="0.01">
  <pointmin x="-1" y="0" z="-1" />
  <pointmax x="4.5" y="0" z="3.5" />
</definition>
```

Even though pointmin.y == pointmax.y == 0, drawing commands still use non-zero y extents
to give objects thickness. **Objects are drawn spanning y=−1 to y=1** — GenCase projects
them onto the 2D plane automatically:

```xml
<!-- 2D floor: y spans −1 to 1 even though domain y=0 -->
<drawbox>
  <boxfill>solid</boxfill>
  <point x="0" y="-1" z="0" />
  <size x="4.0" y="2" z="0.04" />
</drawbox>
```

**Rules for 2D:**
- `pointmin y` and `pointmax y` MUST be the same value (typically 0)
- All drawbox/drawcylinder/etc. use y span (e.g., y=−1 to y=1) for thickness
- `fillbox` seed point y = domain y-value (typically 0)
- Probe y-coordinate = domain y-value (typically 0)

### 3D simulation
- `pointmin.y` and `pointmax.y` span the actual 3D domain
- All objects span their real y-extents

### How to decide 2D vs 3D
- If the user says "2D" or the scenario is a channel/dam break with no lateral variation → **2D**
- If the user describes width, lateral obstacles, or 3D effects → **3D**
- When in doubt, use **2D** (much faster, ~100× fewer particles)

---

## D. MK System

Every particle gets an MK label that identifies its role. Set the current MK before drawing.

| Command | Description |
|---------|-------------|
| `<setmkfluid mk="N" />` | Next drawn particles are fluid with mkfluid=N (0–8) |
| `<setmkbound mk="N" />` | Next drawn particles are boundary with mkbound=N (0–239) |
| `<setmkvoid />` | Next drawn particles are void (erased) — used for carving |
| `<setmknextfluid next="true" />` | Auto-increment mkfluid by 1 |
| `<setmknextbound next="true" />` | Auto-increment mkbound by 1 |
| `<setmknextauto auto="true" />` | After each draw command mk is increased automatically |

**Conventions:**
- `mkfluid=0` is the primary fluid phase
- `mkbound=0` is the primary fixed boundary
- Use distinct mk values for parts you want to track separately (e.g., different walls, floating objects)

---

## E. Drawing Modes

### setdrawmode — how particles are created from shapes
```xml
<setdrawmode mode="full" />
```
| Mode | Effect |
|------|--------|
| `full` | Surface + interior (most common — use by default) |
| `solid` | Interior only |
| `face` | Surface particles only (hollow shell — efficient for large tanks) |
| `wire` | Edges only (wireframe) |

### setshapemode — VTK output for visualisation
```xml
<setshapemode>dp | bound</setshapemode>
```
Combine tokens with `|`: `actual`, `dp`, `bound`, `fluid`, `void`, `null`

### shapeout — write VTK output
```xml
<shapeout file="" />                   <!-- Write default VTK output -->
<shapeout file="Building" />           <!-- Write named VTK file -->
<shapeout file="" reset="true" />      <!-- Write VTK, then clear for next group -->
```

---

## F. Physics Parameters

### constantsdef

| Parameter | Default | Notes |
|-----------|---------|-------|
| `rhop0` | 1000 kg/m³ | Reference fluid density. **Must match phase_rhop.** |
| `gravity_z` | −9.81 m/s² | Change for tilted flume, reduced gravity, etc. |
| `coefh` | 0.91924 | Smoothing length coefficient. Rarely changed. |
| `cflnumber` | 0.1 | CFL multiplier. Lower = more stable, slower. |

### nnphases (non-Newtonian phase parameters)

| Parameter | Meaning | Newtonian | Power-law | Bingham | Dense debris |
|-----------|---------|-----------|-----------|---------|--------------|
| `phase_rhop` | Phase density (kg/m³) | 1000 | 1200–1400 | 1400–1600 | 1600–2000 |
| `visco_nn` | Consistency index (m²/s) | 1e-6 | 0.01–0.1 | 0.01–0.5 | 0.05–1.0 |
| `tau_yield` | Specific yield stress (Pa·m³/kg) | 0 | 0 | 0.005–0.05 | 0.01–0.1 |
| `HBP_m` | Regularisation parameter (s) | 0 | 1–10 | 50–200 | 10–100 |
| `HBP_n` | Flow index | 1.0 | 0.5–0.9 | 1.0 | 0.8–1.2 |

### Material Archetypes

| Description | phase_rhop | visco_nn | tau_yield | HBP_m | HBP_n |
|-------------|-----------|----------|-----------|-------|-------|
| Water | 1000 | 1e-6 | 0 | 0 | 1.0 |
| Thin mudflow (dilute) | 1200 | 0.01 | 0.002 | 10 | 0.9 |
| Moderate mudslide | 1400 | 0.05 | 0.008 | 20 | 1.0 |
| Dense mudslide (Bingham) | 1500 | 0.1 | 0.02 | 100 | 1.0 |
| Debris flow (Herschel-Bulkley) | 1800 | 0.3 | 0.05 | 50 | 1.1 |
| Shear-thinning slurry | 1300 | 0.05 | 0.005 | 10 | 0.7 |
| Very dense dry granular | 2000 | 0.5 | 0.08 | 100 | 1.2 |

**Physical interpretation of HBP_m:**
- `HBP_m = 0`: pure Newtonian (no yield)
- `HBP_m = 1–10`: gentle transition at yield point (power-law-like)
- `HBP_m = 50–200`: sharp yield transition (Bingham-like)

**Physical interpretation of tau_yield:**
- `tau_yield = 0`: material flows freely under any stress
- `tau_yield = 0.005–0.02`: moderate yield — flows like thick mud
- `tau_yield > 0.05`: strong yield — resists flow like wet concrete

### Execution parameters

| Parameter | Default | Notes |
|-----------|---------|-------|
| `TimeMax` | 5.0 s | Total simulation time. Adjust to scenario. |
| `TimeOut` | 0.1 s | Output interval. 0.05–0.2 s typical. |
| `DensityDT` | 3 | Density diffusion: 3=Fourtakas full (best for free surface) |
| `DensityDTvalue` | 0.1 | DDT coefficient. Rarely changed. |
| `Visco` | 1e-6 | Wall viscosity. **Should match visco_nn.** |

---

## G. Probe Placement

### General strategy
Place probes where you expect interesting flow behaviour. Output as `[x, y, z]` triples.

### Heuristics by scenario type

**Channel / dam break (2D):**
- x: 3 points evenly spaced downstream of the initial fluid, clear of walls
- z: 2 heights — near floor (0.05 m) and mid-fluid-height
- y: fixed at 0 (the 2D domain y-value)
- Total: 6 probes

**Tank with obstacle (2D or 3D):**
- Upstream of obstacle (1–2 points)
- Downstream of obstacle (1–2 points)
- Near the obstacle surface (1–2 points)
- Near free surface (1 point)

**Inclined channel / debris flow (2D):**
- Along the slope at regular intervals
- At heights above the slope surface (not below it!)
- Account for the slope when calculating z-position of probes

**Open channel flow:**
- Along the channel at regular intervals
- At multiple heights to capture velocity profile

**General rules:**
- Keep probes at least `3×dp` from any boundary to avoid kernel truncation artefacts
- Keep probes inside the expected fluid domain (not in air or boundary)
- For 2D cases, y = 0
- Return probes as a list of `[x, y, z]` triples

### Example (2D dam break, channel_length=4.0, fluid_width=1.0, fluid_height=1.5):
```
probe_points = [
  [1.5, 0, 0.05],   # downstream, near floor
  [1.5, 0, 0.75],   # downstream, mid-height
  [2.5, 0, 0.05],   # mid-channel, near floor
  [2.5, 0, 0.75],   # mid-channel, mid-height
  [3.5, 0, 0.05],   # far downstream, near floor
  [3.5, 0, 0.75],   # far downstream, mid-height
]
```

---

## H. Reasoning Guidelines

When interpreting a natural language scenario:

1. **Decide 2D or 3D first** — this affects every dimension in your geometry
2. **Identify material type** → pick the closest archetype row as a starting point
3. **Adjust density** based on sediment concentration:
   - "dilute" / "watery" → 1000–1200 kg/m³
   - "moderate" / "muddy" → 1300–1600 kg/m³
   - "dense" / "debris-laden" → 1600–2000 kg/m³
4. **Yield stress cues**:
   - "flows freely", "watery" → tau_yield = 0
   - "thick", "sluggish" → tau_yield = 0.01–0.05
   - "barely flows", "like wet concrete" → tau_yield > 0.05
5. **Shear behaviour cues**:
   - "shear-thinning", "thins under flow" → HBP_n = 0.6–0.9
   - "Newtonian" → HBP_n = 1.0
   - "shear-thickening", "dilatant" → HBP_n = 1.1–1.3
6. **Set `rhop0` = `phase_rhop`** (constantsdef reference density must match the phase)
7. **Set `Visco` = `visco_nn`** (wall viscosity should match phase viscosity)
8. **Geometry**: design from scratch using primitives. Think about:
   - What boundaries are needed (walls, floor, obstacles, slopes)?
   - Where is the fluid initially?
   - Is the floor flat or inclined?
   - What are the domain bounds (pointmin/pointmax with margin)?
9. **Inclined surfaces**: use `drawprism` with matched base/top polygons, or `drawbeach` with profile points. Place fluid via `fillbox` with seed above the slope.
10. **Complex shapes**: if the geometry involves organic/CAD shapes (ship hulls, turbines, terrain), ask the user for an STL file and use `drawfilestl`.

---

## I. Available Resources

Use `read_skill_resource` to load these when needed:

| Resource | When to load | Content |
|---|---|---|
| `drawing-primitives.md` | **Always** — needed for any geometry | All shape commands: boxes, rounded shapes, polyhedrons (prism, beach, extrude), lines, triangles, external geometry (STL/VTK/PLY), fill operations (fillbox, fillpoint), redraw commands |
| `transforms-and-advanced.md` | When geometry requires transforms, variables, reusable lists, or parameterised dimensions | Transform stack, user variables, math expressions, reusable lists, clipping, debugging |
| `composition-patterns.md` | When you need reference examples of common simulation setups | Complete geometry examples: 2D dam break, inclined channel, sloped beach, flood fill, void carving, and more |
