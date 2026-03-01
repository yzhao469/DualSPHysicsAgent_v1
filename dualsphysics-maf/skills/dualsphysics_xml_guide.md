# DualSPHysics GenCase — Comprehensive Geometry & Parameter Reference

You generate the full `<geometry>` XML block for any DualSPHysics scenario.
This reference documents every available drawing command, fill operation,
transform, and composition pattern. Use it to build geometry from first principles.

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
        <pointmin x="-0.5" y="-0.5" z="-0.5" />
        <pointmax x="5.0" y="3.0" z="5.0" />
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
- `dp` = inter-particle distance (m). Controls resolution. Halving dp -> ~4x particles, ~4-8x runtime.
- `<pointmin>` / `<pointmax>` define the domain bounding box. Must enclose all geometry with some margin (~0.2-0.5 m).
- `<mainlist>` is executed top-to-bottom. Order matters — later commands overwrite earlier particles.
- Always end `<mainlist>` with `<shapeout file="" />` to write VTK output.

---

## B. MK System

Every particle gets an MK label that identifies its role. Set the current MK before drawing.

| Command | Description |
|---------|-------------|
| `<setmkfluid mk="N" />` | Next drawn particles are fluid with mkfluid=N (0-8) |
| `<setmkbound mk="N" />` | Next drawn particles are boundary with mkbound=N (0-239) |
| `<setmkvoid />` | Next drawn particles are void (erased) — used for carving |
| `<setmknextfluid />` | Auto-increment mkfluid by 1 |
| `<setmknextbound />` | Auto-increment mkbound by 1 |
| `<setmknextauto mk="N" />` | Set the next auto-mk value |

**Conventions:**
- `mkfluid=0` is the primary fluid phase
- `mkbound=0` is the primary fixed boundary
- Use distinct mk values for parts you want to track separately (e.g., different walls, floating objects)

---

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

---

## E. Transform Stack

Transforms apply to subsequent drawing commands until reset.

| Command | Description |
|---------|-------------|
| `<move x="DX" y="DY" z="DZ" />` | Translate |
| `<rotate angx="AX" angy="AY" angz="AZ" />` | Rotate (degrees, applied in order X->Y->Z) |
| `<rotateline>` | Rotate around an arbitrary axis line |
| `<scale x="SX" y="SY" z="SZ" />` | Scale |
| `<matrixreset />` | Reset transform to identity |
| `<matrixsave id="N" />` | Save current transform |
| `<matrixload id="N" />` | Restore saved transform |

**Usage pattern:**
```xml
<matrixsave id="0" />
<move x="2" y="0" z="0" />
<rotate angx="0" angy="0" angz="45" />
<drawbox> ... </drawbox>
<matrixload id="0" />
```

---

## F. Variables

GenCase supports user-defined variables for parameterised geometry.

```xml
<!-- Define variables -->
<newvar name="TankLen" value="4.0" />
<newvar name="TankH" value="1.5" />
<newvarcte name="Pi" value="3.14159265" />

<!-- Use variables with # prefix -->
<drawbox>
  <point x="0" y="0" z="0" />
  <size x="#TankLen" y="2" z="#TankH" />
</drawbox>
```

**Expressions:** Variables can use arithmetic: `value="2*#TankLen+0.5"`

**Built-in auto-constants:** `_Dp` (particle spacing), `_Gravity_x/y/z`, `_Rhop0`

---

## G. Reusable Lists

Define reusable command groups:

```xml
<commands>
  <list name="WallSegment">
    <drawbox>
      <boxfill>solid</boxfill>
      <point x="0" y="0" z="0" />
      <size x="0.04" y="2" z="1.5" />
    </drawbox>
  </list>
  <mainlist>
    <setmkbound mk="0" />
    <!-- Place the wall at different positions -->
    <move x="0" y="0" z="0" />
    <runlist name="WallSegment" />
    <matrixreset />
    <move x="4.0" y="0" z="0" />
    <runlist name="WallSegment" />
    <matrixreset />
    <shapeout file="" />
  </mainlist>
</commands>
```

`<runlist name="X" times="N" />` — run list X repeatedly N times (default 1).

---

## H. Drawing Modes

| Command | Description |
|---------|-------------|
| `<setshapemode>dp \| bound</setshapemode>` | Standard mode: dp spacing for fluid, bound for boundaries |
| `<setdrawmode mode="full" />` | Full drawing (default) |
| `<setdrawmode mode="face" />` | Only draw surface particles (hollow) |
| `<setactive drawbound="true" drawfluid="true" />` | Enable/disable drawing fluid or boundary |
| `<resetdraw />` | Clear all drawn particles |
| `<shapeout file="" />` | Write VTK output (empty string = default name) |

---

## I. 2D vs 3D

**2D simulation:**
- Set all y-extents to a fixed depth (typically `2.0 m`)
- All objects span the full y-range: `y=0` to `y=2.0`
- Domain: `pointmin y=0`, `pointmax y=2` (or use small margin: `-0.1` to `2.1`)
- Probe y-coordinate: `y=1.0` (centre)

**3D simulation:**
- Full 3D domain with appropriate y-extents
- Set `ShiftTFS` to `2.75` (instead of `1.5` for 2D) in execution parameters

---

## J. Composition Patterns

### J1. Open-top tank (2D)
```xml
<geometry>
  <definition dp="0.01">
    <pointmin x="-0.2" y="-0.1" z="-0.2" />
    <pointmax x="4.5" y="2.1" z="3.0" />
  </definition>
  <commands>
    <mainlist>
      <setshapemode>dp | bound</setshapemode>
      <setdrawmode mode="full" />
      <!-- Floor -->
      <setmkbound mk="0" />
      <drawbox>
        <boxfill>solid</boxfill>
        <point x="0" y="0" z="0" />
        <size x="4.0" y="2" z="0.04" />
      </drawbox>
      <!-- Left wall -->
      <setmkbound mk="1" />
      <drawbox>
        <boxfill>solid</boxfill>
        <point x="0" y="0" z="0" />
        <size x="0.04" y="2" z="1.5" />
      </drawbox>
      <!-- Right wall -->
      <setmkbound mk="2" />
      <drawbox>
        <boxfill>solid</boxfill>
        <point x="3.96" y="0" z="0" />
        <size x="0.04" y="2" z="1.5" />
      </drawbox>
      <!-- Fluid column -->
      <setmkfluid mk="0" />
      <drawbox>
        <boxfill>solid</boxfill>
        <point x="0.04" y="0" z="0.04" />
        <size x="0.8" y="2" z="1.0" />
      </drawbox>
      <shapeout file="" />
    </mainlist>
  </commands>
</geometry>
```

### J2. Dam break (2D)
```xml
<geometry>
  <definition dp="0.01">
    <pointmin x="-0.2" y="-0.1" z="-0.2" />
    <pointmax x="4.5" y="2.1" z="2.5" />
  </definition>
  <commands>
    <mainlist>
      <setshapemode>dp | bound</setshapemode>
      <setdrawmode mode="full" />
      <!-- Floor -->
      <setmkbound mk="0" />
      <drawbox>
        <boxfill>solid</boxfill>
        <point x="0" y="0" z="0" />
        <size x="4.0" y="2" z="0.04" />
      </drawbox>
      <!-- Left wall -->
      <setmkbound mk="1" />
      <drawbox>
        <boxfill>solid</boxfill>
        <point x="-0.04" y="0" z="0" />
        <size x="0.04" y="2" z="2.0" />
      </drawbox>
      <!-- Right wall -->
      <setmkbound mk="2" />
      <drawbox>
        <boxfill>solid</boxfill>
        <point x="4.0" y="0" z="0" />
        <size x="0.04" y="2" z="2.0" />
      </drawbox>
      <!-- Water column (dam) -->
      <setmkfluid mk="0" />
      <drawbox>
        <boxfill>solid</boxfill>
        <point x="0" y="0" z="0.04" />
        <size x="1.0" y="2" z="1.5" />
      </drawbox>
      <shapeout file="" />
    </mainlist>
  </commands>
</geometry>
```

### J3. Void carving (obstacle inside fluid)
```xml
<!-- First draw fluid, then carve out obstacle shape with void, then draw boundary there -->
<setmkfluid mk="0" />
<drawbox>
  <boxfill>solid</boxfill>
  <point x="0" y="0" z="0.04" />
  <size x="4.0" y="2" z="1.0" />
</drawbox>
<!-- Carve void where obstacle will be -->
<setmkvoid />
<drawcylinder radius="0.1">
  <point x="2.0" y="0" z="0.5" />
  <point x="2.0" y="2" z="0.5" />
</drawcylinder>
<!-- Draw obstacle as boundary -->
<setmkbound mk="3" />
<drawcylinder radius="0.1">
  <point x="2.0" y="0" z="0.5" />
  <point x="2.0" y="2" z="0.5" />
</drawcylinder>
```

### J4. Flood fill (fill enclosed region with fluid)
```xml
<!-- Draw walls first, then flood-fill the interior -->
<setmkbound mk="0" />
<drawbox>
  <boxfill>bottom | left | right</boxfill>
  <point x="0" y="0" z="0" />
  <size x="3.0" y="2" z="1.0" />
</drawbox>
<setmkfluid mk="0" />
<fillbox x="1.5" y="1.0" z="0.3">
  <modefill>void</modefill>
  <point x="0.04" y="0" z="0.04" />
  <size x="2.92" y="2" z="0.5" />
</fillbox>
```

### J5. Sloped beach / ramp
```xml
<!-- Sloped bottom using drawprism (triangle cross-section) -->
<setmkbound mk="4" />
<drawprism mask="0">
  <point x="3.0" y="0" z="0.04" />
  <point x="5.0" y="0" z="0.04" />
  <point x="5.0" y="0" z="0.8" />
  <point x="3.0" y="2" z="0.04" />
  <point x="5.0" y="2" z="0.04" />
  <point x="5.0" y="2" z="0.8" />
</drawprism>
```

### J6. External mesh (STL obstacle)
```xml
<setmkbound mk="5" />
<drawfilestl file="obstacle.stl" objname="">
  <drawscale x="0.001" y="0.001" z="0.001" />
  <drawmove x="2.0" y="1.0" z="0.5" />
</drawfilestl>
```

### J7. Repeated objects (array of pillars)
```xml
<commands>
  <list name="Pillar">
    <drawcylinder radius="0.05">
      <point x="0" y="0" z="0" />
      <point x="0" y="2" z="1.0" />
    </drawcylinder>
  </list>
  <mainlist>
    <setshapemode>dp | bound</setshapemode>
    <setdrawmode mode="full" />
    <setmkbound mk="10" />
    <!-- Place pillars at x = 1.0, 2.0, 3.0 -->
    <move x="1.0" y="0" z="0" />
    <runlist name="Pillar" />
    <matrixreset />
    <move x="2.0" y="0" z="0" />
    <runlist name="Pillar" />
    <matrixreset />
    <move x="3.0" y="0" z="0" />
    <runlist name="Pillar" />
    <matrixreset />
    <shapeout file="" />
  </mainlist>
</commands>
```

### J8. Multi-phase (two fluids)
```xml
<!-- Phase 0: water -->
<setmkfluid mk="0" />
<drawbox>
  <boxfill>solid</boxfill>
  <point x="0" y="0" z="0.04" />
  <size x="2.0" y="2" z="0.5" />
</drawbox>
<!-- Phase 1: oil (lighter, on top) -->
<setmkfluid mk="1" />
<drawbox>
  <boxfill>solid</boxfill>
  <point x="0" y="0" z="0.54" />
  <size x="2.0" y="2" z="0.3" />
</drawbox>
```
Each phase needs a corresponding `<phase mkfluid="N">` in `<nnphases>`.

### J9. 3D tank with obstacle
```xml
<geometry>
  <definition dp="0.02">
    <pointmin x="-0.5" y="-0.5" z="-0.5" />
    <pointmax x="5.0" y="3.0" z="3.0" />
  </definition>
  <commands>
    <mainlist>
      <setshapemode>dp | bound</setshapemode>
      <setdrawmode mode="full" />
      <!-- Tank walls (all 5 faces, open top) -->
      <setmkbound mk="0" />
      <drawbox>
        <boxfill>bottom | left | right | front | back</boxfill>
        <point x="0" y="0" z="0" />
        <size x="4.0" y="2.0" z="2.0" />
      </drawbox>
      <!-- Obstacle (sphere) -->
      <setmkbound mk="1" />
      <drawsphere radius="0.15">
        <point x="2.5" y="1.0" z="0.3" />
      </drawsphere>
      <!-- Fluid -->
      <setmkfluid mk="0" />
      <drawbox>
        <boxfill>solid</boxfill>
        <point x="0.04" y="0.04" z="0.04" />
        <size x="1.0" y="1.92" z="1.0" />
      </drawbox>
      <shapeout file="" />
    </mainlist>
  </commands>
</geometry>
```

---

## K. Physics Parameters

### constantsdef

| Parameter | Default | Notes |
|-----------|---------|-------|
| `rhop0` | 1000 kg/m^3 | Reference fluid density. **Must match phase_rhop.** |
| `gravity_z` | -9.81 m/s^2 | Change for tilted flume, reduced gravity, etc. |
| `coefh` | 0.91924 | Smoothing length coefficient. Rarely changed. |
| `cflnumber` | 0.1 | CFL multiplier. Lower = more stable, slower. |

### nnphases (non-Newtonian phase parameters)

| Parameter | Meaning | Newtonian | Power-law | Bingham | Dense debris |
|-----------|---------|-----------|-----------|---------|--------------|
| `phase_rhop` | Phase density (kg/m^3) | 1000 | 1200-1400 | 1400-1600 | 1600-2000 |
| `visco_nn` | Consistency index (m^2/s) | 1e-6 | 0.01-0.1 | 0.01-0.5 | 0.05-1.0 |
| `tau_yield` | Specific yield stress (Pa.m^3/kg) | 0 | 0 | 0.005-0.05 | 0.01-0.1 |
| `HBP_m` | Regularisation parameter (s) | 0 | 1-10 | 50-200 | 10-100 |
| `HBP_n` | Flow index | 1.0 | 0.5-0.9 | 1.0 | 0.8-1.2 |

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
- `HBP_m = 1-10`: gentle transition at yield point (power-law-like)
- `HBP_m = 50-200`: sharp yield transition (Bingham-like)

**Physical interpretation of tau_yield:**
- `tau_yield = 0`: material flows freely under any stress
- `tau_yield = 0.005-0.02`: moderate yield — flows like thick mud
- `tau_yield > 0.05`: strong yield — resists flow like wet concrete

### Execution parameters

| Parameter | Default | Notes |
|-----------|---------|-------|
| `TimeMax` | 5.0 s | Total simulation time. Adjust to scenario. |
| `TimeOut` | 0.1 s | Output interval. 0.05-0.2 s typical. |
| `DensityDT` | 3 | Density diffusion: 3=Fourtakas full (best for free surface) |
| `DensityDTvalue` | 0.1 | DDT coefficient. Rarely changed. |
| `Visco` | 1e-6 | Wall viscosity. **Should match visco_nn.** |

---

## L. Probe Placement

### General strategy
Place probes where you expect interesting flow behaviour. Output as `[x, y, z]` triples.

### Heuristics by scenario type

**Channel / dam break (2D):**
- x: 3 points evenly spaced downstream of the initial fluid, clear of walls
- z: 2 heights — near floor (0.05 m) and mid-fluid-height
- y: fixed at domain centre (e.g., 1.0 for y-depth of 2.0)
- Total: 6 probes

**Tank with obstacle (2D or 3D):**
- Upstream of obstacle (1-2 points)
- Downstream of obstacle (1-2 points)
- Near the obstacle surface (1-2 points)
- Near free surface (1 point)

**Open channel flow:**
- Along the channel at regular intervals
- At multiple heights to capture velocity profile

**General rules:**
- Keep probes at least `3*dp` from any boundary to avoid kernel truncation artefacts
- Keep probes inside the expected fluid domain (not in air or boundary)
- For 2D cases, y should be at domain centre
- Return probes as a list of `[x, y, z]` triples

### Example (2D dam break, channel_length=4.0, fluid_width=1.0, fluid_height=1.5):
```
probe_points = [
  [1.5, 1.0, 0.05],   # downstream, near floor
  [1.5, 1.0, 0.75],   # downstream, mid-height
  [2.5, 1.0, 0.05],   # mid-channel, near floor
  [2.5, 1.0, 0.75],   # mid-channel, mid-height
  [3.5, 1.0, 0.05],   # far downstream, near floor
  [3.5, 1.0, 0.75],   # far downstream, mid-height
]
```

---

## Reasoning Guidelines

When interpreting a natural language scenario:

1. **Identify material type** -> pick the closest archetype row as a starting point
2. **Adjust density** based on sediment concentration:
   - "dilute" / "watery" -> 1000-1200 kg/m^3
   - "moderate" / "muddy" -> 1300-1600 kg/m^3
   - "dense" / "debris-laden" -> 1600-2000 kg/m^3
3. **Yield stress cues**:
   - "flows freely", "watery" -> tau_yield = 0
   - "thick", "sluggish", "won't flow without force" -> tau_yield = 0.01-0.05
   - "barely flows", "like wet concrete" -> tau_yield > 0.05
4. **Shear behaviour cues**:
   - "shear-thinning", "thins under flow" -> HBP_n = 0.6-0.9
   - "Newtonian" -> HBP_n = 1.0
   - "shear-thickening", "dilatant" -> HBP_n = 1.1-1.3
5. **Set `rhop0` = `phase_rhop`** (constantsdef reference density must match the phase)
6. **Set `Visco` = `visco_nn`** (wall viscosity should match phase viscosity)
7. **Geometry**: design from scratch using the primitives above. Think about:
   - What boundaries are needed (walls, floor, obstacles)?
   - Where is the fluid initially?
   - What are the domain bounds (pointmin/pointmax)?
   - Is this 2D or 3D?
8. **Complex shapes**: if the geometry involves organic/CAD shapes (ship hulls, turbines, terrain), ask the user for an STL file and use `drawfilestl`.
