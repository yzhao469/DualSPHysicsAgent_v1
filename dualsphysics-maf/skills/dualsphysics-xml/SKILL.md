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
    <!-- Optional: floating bodies go here (see Section D2) -->
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
- `mkbound=0–49` → fixed or moving boundaries
- `mkbound=50–239` → floating bodies (see Section D2)
- Use distinct mk values for parts you want to track separately (e.g., different walls, floating objects)

### D2. Floating Bodies — IMPORTANT

Floating bodies are boundary particles that move freely under fluid forces and gravity.
Creating a floating body requires **two things**:

1. **Use `mkbound >= 50`** in the geometry drawing commands. Each separate floating object
   must have its own unique mkbound value (e.g., 50, 51, 52, ...).

2. **Add a `<floatings>` section** inside `<casedef>`, after `</geometry>` and before `</casedef>`.
   Each floating body must be declared with its mkbound and mass:

```xml
<geometry>
  <!-- ... drawing commands ... -->
</geometry>
<floatings>
    <floating mkbound="50">
        <massbody value="500000" />
    </floating>
    <floating mkbound="51">
        <massbody value="500000" />
    </floating>
</floatings>
```

**Both are required.** Using `mkbound >= 50` without the `<floatings>` declaration will make
GenCase treat the particles as fixed boundaries. The `<floatings>` section tells DualSPHysics
to treat those particles as rigid bodies that respond to fluid forces.

**How to include in `geometry_xml`:**
Include `<floatings>` right after `</geometry>` in your `geometry_xml` output. The
`set_geometry` tool will automatically detect and place both elements correctly. Example:

```xml
<geometry>
  <!-- ... drawing commands ... -->
</geometry>
<floatings>
    <floating mkbound="50"><massbody value="500000" /></floating>
    <floating mkbound="51"><massbody value="500000" /></floating>
</floatings>
```

**`massbody`** is the total mass of the floating object in kg. Estimate from:
`massbody = density × volume` (e.g., concrete block 1m³ at 2400 kg/m³ → massbody=2400).

**Optional floating parameters:**
```xml
<floating mkbound="50">
    <massbody value="500" />
    <center x="10" y="3" z="4" />           <!-- Override center of mass -->
    <inertia x="100" y="100" z="100" />     <!-- Moments of inertia (kg·m²) -->
    <linearvelini x="0" y="0" z="0" />      <!-- Initial linear velocity -->
    <angularvelini x="0" y="0" z="0" />     <!-- Initial angular velocity -->
</floating>
```

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

## F. Physics Parameters & Parameterization

All parameters scale from `dp` (defined in Section B). The following subsections define
how to set each parameter and how they interact.

### F1. Smoothing Length (`coefh`) — CRITICAL PARAMETER

**Definition:** `h = coefh × √3 × dp`

Physical meaning:
- Defines kernel support radius
- Controls: neighbor count, numerical stability, boundary interaction quality

| Case | coefh |
|------|-------|
| Standard SPH | 1.0 |
| High accuracy | 1.2–1.5 |
| Coarse/fast | 0.8–1.0 (risky) |

**Key Rule — Boundary Thickness MUST Match `h`:**
SPH requires full kernel support near walls. Required wall thickness ≥ 2h (minimum), 3h (recommended).
Convert to particle layers: `N_layers ≈ 2h / dp = 2 × coefh × √3`.
Once `coefh` is selected: compute `h = coefh * sqrt(3) * dp`, then enforce `boundary_layers >= ceil(2h / dp)`.
For `coefh = 1`, **3 boundary layers** is generally accepted.
Use `<layers vdp="0,1,2" />` inside `<drawbox>` to create 3 layers when using `boxfill` face selection.

### F2. CFL Number (`cflnumber`)

Controls time step: `Δt ∝ CFL × h / (c + u_max)`

| Case | CFL |
|------|-----|
| Stable | 0.1–0.2 |
| Aggressive | 0.2–0.3 |

Default: **0.15–0.2**. Reduce if high viscosity, strong yield stress, or high velocity gradients.

### F3. Speed of Sound (`coefsound`)

**Definition:** `c = coefsound × U_max`

Controls compressibility error. Must ensure `U_max / c < 0.1`.

| Flow type | coefsound |
|-----------|-----------|
| Weakly compressible SPH | 10–20 |
| Highly dynamic | 20–30 |

### F4. Artificial Viscosity (`Visco`)

From `<parameter key="Visco" value="..." />`. This is **NOT** physical viscosity (which comes from `<visco value="..." />`).

Role: numerical stabilization, shock damping, prevents particle interpenetration.

| Case | Visco |
|------|-------|
| General debris flow | 0.05–0.2 |
| Violent flow | 0.2–0.4 |
| Water/Newtonian | 1e-6 |
| High-resolution | ↓ with dp |

Default: `Visco ≈ 0.1` for debris flow. Scale with resolution: `Visco ∝ dp`.

### F5. Coupled Parameter Logic (VERY IMPORTANT)

Agent must ensure consistency across parameters:

**If `coefh` increases:**
- → `h` will increase
- → Need more boundary layers

**If `coefsound` increases:**
- → `dt` should decrease
- → More stable pressure
- → More expensive

**If `Visco` increases:**
- → More damping
- → Slower flow
- → May suppress physics

### F6. constantsdef — Other Parameters

| Parameter | Default | Notes |
|-----------|---------|-------|
| `rhop0` | 1000 kg/m³ | Reference fluid density. **Must match phase_rhop.** |
| `gravity_z` | −9.81 m/s² | Change for tilted flume, reduced gravity, etc. |

### F7. nnphases (non-Newtonian phase parameters)

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

### F8. Execution parameters

| Parameter | Default | Notes |
|-----------|---------|-------|
| `TimeMax` | 5.0 s | Total simulation time. Adjust to scenario. |
| `TimeOut` | 0.1 s | Output interval. 0.05–0.2 s typical. |
| `DensityDT` | 3 | Density diffusion: 3=Fourtakas full (best for free surface) |
| `DensityDTvalue` | 0.1 | DDT coefficient. Rarely changed. |
| `Visco` | — | See F4 for details and recommended values. |

---

## G. Reasoning Guidelines

### Agent Workflow (Recommended Steps)

1. **Decide 2D or 3D** — this affects every dimension in your geometry.
2. **Define resolution** — choose `dp` to avoid too many or too limited particles.
3. **Set smoothing** — `coefh` → 1.0 (default). Compute `h = coefh * sqrt(3) * dp`.
4. **Build boundaries** — enforce boundary thickness per F1 (≥ `ceil(2h/dp)` layers, typically 3).
5. **Set physics** — `coefsound = 10–20`, `cflnumber = 0.15–0.2`, `Visco = 0.1` (see F2–F4).
6. **Set rheology (if HBP)** — `visco` (K), `tau_yield`, `HBP_n`.

### Interpreting Natural Language Scenarios

1. **Identify material type** → pick the closest archetype row (F7) as a starting point.
2. **Adjust density** based on sediment concentration:
   - "dilute" / "watery" → 1000–1200 kg/m³
   - "moderate" / "muddy" → 1300–1600 kg/m³
   - "dense" / "debris-laden" → 1600–2000 kg/m³
3. **Yield stress cues**:
   - "flows freely", "watery" → tau_yield = 0
   - "thick", "sluggish" → tau_yield = 0.01–0.05
   - "barely flows", "like wet concrete" → tau_yield > 0.05
4. **Shear behaviour cues**:
   - "shear-thinning", "thins under flow" → HBP_n = 0.6–0.9
   - "Newtonian" → HBP_n = 1.0
   - "shear-thickening", "dilatant" → HBP_n = 1.1–1.3
5. **Set `rhop0` = `phase_rhop`** (constantsdef reference density must match the phase).
6. **Set `Visco` = `visco_nn`** — match phase viscosity. Default 0.1 for debris flow, 1e-6 for water.

### Geometry Design

1. **Build geometry** from primitives. Think about:
   - What boundaries are needed (walls, floor, obstacles, slopes)?
   - Boundary thickness per F1: use `drawmode="full"` (default) with shape thickness ≥ `ceil(2h/dp) × dp`.
   - Where is the fluid initially?
   - Is the floor flat or inclined?
   - What are the domain bounds (pointmin/pointmax with margin)?
2. **Draw order matters**: later draw commands overwrite earlier particles at the same position.
   Draw fluid BEFORE boundaries so that wall particles overwrite fluid at shared positions,
   not the other way around. Alternatively, use `boxfill` face selection for walls (see below).
3. **Inclined surfaces**: use `drawprism` with matched base/top polygons, or `drawbeach` with profile points. Place fluid via `fillbox` with seed above the slope.
4. **Complex shapes**: if the geometry involves organic/CAD shapes (ship hulls, turbines, terrain), ask the user for an STL file and use `drawfilestl`.

### Wall Construction — CRITICAL

**You MUST use `boxfill` with face selection** for tank/channel walls. **NEVER draw walls
as separate solid boxes.** The correct pattern is:

1. Draw **fluid first** (`setmkfluid`)
2. Then draw **walls after** using `boxfill` face selection (`setmkbound`)

This way wall particles overwrite fluid at shared positions (not the reverse).

```xml
<!-- CORRECT: fluid first, then walls with boxfill + layers -->
<setmkfluid mk="0" />
<drawbox>
    <boxfill>solid</boxfill>
    <point x="85" y="0" z="0" />
    <size x="15" y="20" z="30" />
</drawbox>
<setmkbound mk="0" />
<drawbox>
    <boxfill>bottom | left | right | front | back</boxfill>
    <point x="0" y="0" z="0" />
    <size x="100" y="20" z="40" />
    <layers vdp="0,1,2" />
</drawbox>
```

**`<layers vdp="0,1,2" />`** creates 3 boundary layers (at dp offsets 0, 1, 2 inward from
each face). This is required for `coefh=1.0` (see Section F1). Without `<layers>`, `boxfill`
creates only a single-particle-thick shell, which is too thin for SPH kernel support.

**NEVER do this:**
```xml
<!-- WRONG: solid boxes for walls — causes fluid to overwrite wall particles -->
<setmkbound mk="0" />
<drawbox><boxfill>solid</boxfill><point x="0" y="0" z="0"/><size x="100" y="20" z="2"/></drawbox>
<drawbox><boxfill>solid</boxfill><point x="0" y="0" z="0"/><size x="2" y="20" z="40"/></drawbox>
<setmkfluid mk="0" />
<drawbox><boxfill>solid</boxfill><point x="0" y="0" z="0"/><size x="15" y="20" z="30"/></drawbox>
<!-- Fluid at z=0 overwrites floor's top layer → boundary gap -->
```

---

## H. Available Resources

Use `read_skill_resource` to load these when needed:

| Resource | When to load | Content |
|---|---|---|
| `drawing-shapes.md` | **Always** — needed for any geometry | All shape commands: boxes, rounded shapes, polyhedrons (prism, pyramid, beach, extrude, figure), lines, triangles, external geometry (STL/VTK/PLY) with mask system reference |
| `fill-and-modification.md` | **Always** — needed when placing fluid | Fill operations (fillbox, fillpoint, fillprism), redraw commands for patching holes, freedraw mode, and multi-layer shell creation |
| `transforms-and-variables.md` | When geometry requires transforms, variables, reusable lists, or parameterised dimensions | Transform stack, user variables, math expressions & functions, reusable lists, clipping, debugging & output |
| `composition-patterns.md` | When you need reference examples of common simulation setups | 11 complete geometry examples: 2D dam break, inclined channel, sloped beach, flood fill, void carving, and more |
