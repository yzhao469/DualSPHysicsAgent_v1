# DualSPHysics DebrisFlow2D — XML Parameter Guide

## Case Topology (FIXED)

The DebrisFlow2D case has a fixed geometry topology:
- **1 fluid phase** (`mkfluid=0`): a rectangular box of non-Newtonian material
- **3 boundary walls**: floor (`mk=11`), left wall (`mk=12`), right wall (`mk=13`)
- **2D case**: y-depth is fixed at `2.0 m` — do NOT change it
- The fluid column sits at the left end of the channel (origin `x=0, z=0`)

---

## Geometry Parameters

| Variable        | XML location                          | Meaning                          | Default | Typical range |
|-----------------|---------------------------------------|----------------------------------|---------|---------------|
| dp              | `<definition dp=...>`                 | Particle spacing (resolution)    | 0.01    | 0.008–0.02 m  |
| fluid_size_x    | fluid drawbox `<size x=...>`          | Fluid column width               | 0.8     | 0.3–1.5 m     |
| fluid_size_z    | fluid drawbox `<size z=...>`          | Fluid column height              | 1.0     | 0.3–2.0 m     |
| channel_length  | floor drawbox `<size x=...>`          | Channel floor length             | 4.0     | 2.0–8.0 m     |
| channel_height  | left/right wall `<size z=...>`        | Wall height (both walls)         | 1.25    | 0.8–3.0 m     |

**Rules:**
- `channel_height` must be > `fluid_size_z` (walls must be taller than the fluid)
- The right wall x-position is auto-updated to `channel_length - 0.04` when you set `channel_length`
- `dp` controls resolution and simulation cost: halving dp increases particle count ~4x and runtime ~4–8x

---

## constantsdef Parameters

| Parameter | XML location                        | Meaning                          | Default | Notes                              |
|-----------|-------------------------------------|----------------------------------|---------|------------------------------------|
| rhop0     | `<rhop0 value=...>`                 | Reference fluid density (kg/m³)  | 1200    | Should match `phase_rhop`          |
| gravity_z | `<gravity z=...>`                   | Gravitational acceleration (m/s²)| -9.81   | Change for tilted flume (e.g. -5)  |
| coefh     | `<coefh value=...>`                 | Smoothing length coefficient     | 0.91924 | Rarely changed                     |
| cflnumber | `<cflnumber value=...>`             | CFL timestep multiplier          | 0.1     | Lower = more stable but slower     |

---

## Non-Newtonian Phase Parameters (`nnphases`, mkfluid=0)

| Parameter  | Meaning                                          | Newtonian | Power-law  | Bingham     | Dense debris |
|------------|--------------------------------------------------|-----------|------------|-------------|--------------|
| phase_rhop | Phase density (kg/m³)                            | 1000      | 1200–1400  | 1400–1600   | 1600–2000    |
| visco_nn   | Consistency index (m²/s)                         | 1e-6      | 0.01–0.1   | 0.01–0.5    | 0.05–1.0     |
| tau_yield  | Specific yield stress (Pa·m³/kg)                 | 0         | 0          | 0.005–0.05  | 0.01–0.1     |
| HBP_m      | Regularisation parameter (s): how sharp the yield transition is | 0 | 1–10 | 50–200  | 10–100       |
| HBP_n      | Flow index: `<1` shear-thinning, `>1` shear-thickening | 1.0 | 0.5–0.9 | 1.0     | 0.8–1.2      |

### Material Archetypes

| Description                  | phase_rhop | visco_nn | tau_yield | HBP_m | HBP_n |
|------------------------------|-----------|----------|-----------|-------|-------|
| Water                        | 1000      | 1e-6     | 0         | 0     | 1.0   |
| Thin mudflow (dilute)        | 1200      | 0.01     | 0.002     | 10    | 0.9   |
| Moderate mudslide            | 1400      | 0.05     | 0.008     | 20    | 1.0   |
| Dense mudslide (Bingham)     | 1500      | 0.1      | 0.02      | 100   | 1.0   |
| Debris flow (Herschel-Bulkley)| 1800     | 0.3      | 0.05      | 50    | 1.1   |
| Shear-thinning slurry        | 1300      | 0.05     | 0.005     | 10    | 0.7   |
| Very dense dry granular      | 2000      | 0.5      | 0.08      | 100   | 1.2   |

**Physical interpretation of HBP_m:**
- `HBP_m = 0`: pure Newtonian (no yield)
- `HBP_m = 1–10`: gentle transition at yield point (power-law-like)
- `HBP_m = 50–200`: sharp yield transition (Bingham-like)

**Physical interpretation of tau_yield:**
- `tau_yield = 0`: material flows freely under any stress (no yield)
- `tau_yield = 0.005–0.02`: moderate yield — flows like thick mud
- `tau_yield > 0.05`: strong yield — material resists flow like wet concrete

---

## Simulation Time Parameters

| Parameter     | Meaning                          | Default | Notes                                    |
|---------------|----------------------------------|---------|------------------------------------------|
| TimeMax       | Total simulation time (s)        | 5.0     | Debris flow typically needs 2–5 s        |
| TimeOut       | Output interval (s)              | 0.1     | 0.05–0.2 s; more outputs = larger files  |
| DensityDT     | Density diffusion scheme         | 3       | 3 = Fourtakas full; best for free surface|
| DensityDTvalue| DDT coefficient                  | 0.1     | Rarely changed                           |
| Visco         | Wall viscosity (artificial)      | 0.1     | Should match `visco_nn` for the phase    |

---

## Probe Point Scheme (Option B — relative to geometry)

Probes are placed relative to the geometry so they are always inside the domain
and physically meaningful. Compute absolute coordinates in Phase 1.

**x positions** — 3 points evenly spaced in the downstream region:
```
x_start = fluid_size_x + 0.2        # just downstream of the initial column
x_end   = channel_length - 0.3      # clear of the right wall
probe_xs = linspace(x_start, x_end, 3)
```

**z positions** — 2 heights per x:
```
z_near_floor = 0.05                  # fixed: just above the floor
z_mid        = fluid_size_z / 2.0   # mid-height of initial fluid column
probe_zs = [z_near_floor, z_mid]
```

**y position** — always `1.0` (centre of the fixed 2D depth).

Total probes: 3 x-positions × 2 z-heights = **6 probes**.

Example (default geometry: fluid_size_x=0.8, fluid_size_z=1.0, channel_length=4.0):
```
probe_xs = [1.0, 2.35, 3.7]
probe_zs = [0.05, 0.5]
```

---

## Reasoning Guidelines

When interpreting a natural language scenario:

1. **Identify material type** → pick the closest archetype row as a starting point
2. **Adjust density** based on sediment concentration:
   - "dilute" / "watery" → 1000–1200 kg/m³
   - "moderate" / "muddy" → 1300–1600 kg/m³
   - "dense" / "debris-laden" → 1600–2000 kg/m³
3. **Yield stress cues**:
   - "flows freely", "watery" → tau_yield = 0
   - "thick", "sluggish", "won't flow without force" → tau_yield = 0.01–0.05
   - "barely flows", "like wet concrete" → tau_yield > 0.05
4. **Shear behaviour cues**:
   - "shear-thinning", "thins under flow" → HBP_n = 0.6–0.9
   - "Newtonian" → HBP_n = 1.0
   - "shear-thickening", "dilatant" → HBP_n = 1.1–1.3
5. **Set `rhop0` = `phase_rhop`** (constantsdef reference density must match the phase)
6. **Set `Visco` = `visco_nn`** (wall viscosity should match phase viscosity)
7. **Geometry**: if a column height or channel length is mentioned, use it; otherwise keep defaults
8. **Explain your parameter choices** in a table before calling `modify_xml`
