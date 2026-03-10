# Composition Patterns

Complete geometry examples for common DualSPHysics simulation setups.
All 2D examples use the correct convention: `pointmin y=0, pointmax y=0`,
with objects drawn spanning `y=-1` to `y=1`.

---

## J1. 2D Dam Break (flat bottom)
The most basic setup: fluid column collapses in a flat-bottomed channel.

```xml
<geometry>
  <definition dp="0.01">
    <pointmin x="-1" y="0" z="-1" />
    <pointmax x="4.5" y="0" z="3.5" />
  </definition>
  <commands>
    <mainlist>
      <setdrawmode mode="full" />
      <!-- Fluid column (dam) -->
      <setmkfluid mk="0" />
      <drawbox>
        <boxfill>solid</boxfill>
        <point x="0" y="-1" z="0" />
        <size x="1" y="2" z="2" />
      </drawbox>
      <!-- Tank: floor + left + right + front + back walls -->
      <setmkbound mk="0" />
      <drawbox>
        <boxfill>bottom | left | right | front | back</boxfill>
        <point x="0" y="-1" z="0" />
        <size x="4" y="2" z="3" />
      </drawbox>
      <shapeout file="" />
    </mainlist>
  </commands>
</geometry>
```

**Key points:**
- `pointmin y=0, pointmax y=0` — this makes it 2D
- Objects span `y=-1` to `y=1` (point y=-1, size y=2) — GenCase handles the projection
- Fluid is drawn BEFORE boundaries (boundaries overwrite fluid at overlaps)
- `boxfill` with 5 faces creates an open-top container

---

## J2. 2D Open-top Channel with Separate Walls

When you need distinct mk labels for each wall (e.g., for force measurement).

```xml
<geometry>
  <definition dp="0.01">
    <pointmin x="-1" y="0" z="-1" />
    <pointmax x="4.5" y="0" z="2.5" />
  </definition>
  <commands>
    <mainlist>
      <setshapemode>dp | bound</setshapemode>
      <setdrawmode mode="full" />
      <!-- Floor -->
      <setmkbound mk="0" />
      <drawbox>
        <boxfill>solid</boxfill>
        <point x="0" y="-1" z="0" />
        <size x="4.0" y="2" z="0.04" />
      </drawbox>
      <!-- Left wall -->
      <setmkbound mk="1" />
      <drawbox>
        <boxfill>solid</boxfill>
        <point x="-0.04" y="-1" z="0" />
        <size x="0.04" y="2" z="2.0" />
      </drawbox>
      <!-- Right wall -->
      <setmkbound mk="2" />
      <drawbox>
        <boxfill>solid</boxfill>
        <point x="4.0" y="-1" z="0" />
        <size x="0.04" y="2" z="2.0" />
      </drawbox>
      <!-- Fluid column -->
      <setmkfluid mk="0" />
      <drawbox>
        <boxfill>solid</boxfill>
        <point x="0" y="-1" z="0.04" />
        <size x="1.0" y="2" z="1.5" />
      </drawbox>
      <shapeout file="" />
    </mainlist>
  </commands>
</geometry>
```

**Key points:**
- Separate mk values for floor (0), left wall (1), right wall (2) — useful for force measurement
- Wall thickness ~0.04 m (≈ 4×dp)
- Fluid starts at z=0.04 (just above the floor surface)

---

## J3. 2D Inclined Channel with Slope (drawprism + fillbox)

A slope/ramp created with `drawprism`, with fluid placed using flood-fill.
This is the standard pattern for debris flow chutes, wave runup, etc.

```xml
<geometry>
  <definition dp="0.02">
    <pointmin x="-1" y="0" z="-1" />
    <pointmax x="25" y="0" z="2" />
  </definition>
  <commands>
    <mainlist>
      <setshapemode>real | dp | bound</setshapemode>
      <setdrawmode mode="full" />
      <!-- Left wall (piston/wavemaker placeholder) -->
      <setmkbound mk="10" />
      <drawbox>
        <boxfill>solid</boxfill>
        <point x="-0.05" y="-1" z="0" />
        <size x="0.05" y="2" z="1.0" />
      </drawbox>
      <!-- Sloped bottom: flat from x=-0.5 to x=9, then ramp up to z=1.0 at x=19 -->
      <setmkbound mk="0" />
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
      <!-- Fluid: flood-fill above the slope -->
      <setmkfluid mk="0" />
      <fillbox x="0.5" y="0" z="0.05">
        <modefill>void</modefill>
        <point x="-1" y="-1" z="-1" />
        <size x="20" y="2" z="1.66" />
      </fillbox>
      <shapeout file="" reset="true" />
    </mainlist>
  </commands>
</geometry>
```

**Key points:**
- `drawprism` with 8 points: first 4 at y=-1, last 4 at y=1 (mirror)
- Points define the cross-section in the XZ plane — varying z along x creates the slope
- `mask="1 | 2 | 6 | 7"` draws only the surface faces (not the interior fill)
- `fillbox` seeds at (0.5, 0, 0.05) — a point above the flat portion of the slope
- The fillbox fills all connected void space bounded by the prism surface

---

## J4. 2D Beach/Slope with drawbeach

`drawbeach` is an alternative to `drawprism` — it takes a profile of (x,z) points
extruded symmetrically about y=0.

```xml
<geometry>
  <definition dp="0.01">
    <pointmin x="-1" y="0" z="-1" />
    <pointmax x="12" y="0" z="1" />
  </definition>
  <commands>
    <mainlist>
      <setshapemode>real | dp | bound</setshapemode>
      <setdrawmode mode="full" />
      <!-- Beach profile: flat from x=-0.2 to x=8, slope up to z=0.4 at x=10 -->
      <setmkbound mk="0" />
      <drawbeach mask="1|2|6">
        <point x="-0.2" y="2" z="0" />
        <point x="8"    y="2" z="0" />
        <point x="10"   y="2" z="0.4" />
        <point x="10"   y="2" z="0.45" />
      </drawbeach>
      <!-- Fluid: flood-fill above the beach -->
      <setmkfluid mk="0" />
      <fillbox x="0.25" y="0" z="0.05">
        <modefill>void</modefill>
        <point x="0" y="-1" z="-1" />
        <size x="11" y="2" z="1.27" />
      </fillbox>
      <shapeout file="" reset="true" />
    </mainlist>
  </commands>
</geometry>
```

**Key points:**
- `drawbeach` points define the XZ profile; the y-value controls extrusion half-width
- `mask="1|2|6"` = bottom + sides + top surfaces
- Fluid is flood-filled above the beach, seeded at a point in the void region

---

## J5. 2D Debris Flow on Inclined Channel

A realistic debris flow scenario: fluid column on a slope with containment walls.
Based on the actual DebrisFlow2D ground truth case.

```xml
<geometry>
  <definition dp="0.01">
    <pointmin x="-0.2" y="0" z="-0.2" />
    <pointmax x="8.15" y="0" z="4.15" />
  </definition>
  <commands>
    <mainlist>
      <setshapemode>dp | bound</setshapemode>
      <setdrawmode mode="full" />
      <!-- Debris fluid column -->
      <setmkfluid mk="0" />
      <drawbox>
        <boxfill>solid</boxfill>
        <point x="0" y="-1" z="0" />
        <size x="0.5" y="2" z="1.0" />
      </drawbox>
      <!-- Floor -->
      <setmkbound mk="11" />
      <drawbox>
        <boxfill>solid</boxfill>
        <point x="0" y="-1" z="0" />
        <size x="4.0" y="2" z="0.04" />
      </drawbox>
      <!-- Left wall -->
      <setmkbound mk="12" />
      <drawbox>
        <boxfill>solid</boxfill>
        <point x="0" y="-1" z="0" />
        <size x="0.04" y="2" z="1.25" />
      </drawbox>
      <!-- Right wall -->
      <setmkbound mk="13" />
      <drawbox>
        <boxfill>solid</boxfill>
        <point x="3.96" y="-1" z="0" />
        <size x="0.04" y="2" z="1.25" />
      </drawbox>
      <shapeout file="" />
    </mainlist>
  </commands>
</geometry>
```

**Note:** For a truly inclined channel, you can either:
1. Tilt the entire geometry using `drawprism` for the floor (see J3)
2. Use `gravity` with x/z components to simulate a tilted flume on a flat geometry

---

## J6. Void Carving (obstacle inside fluid)

Draw fluid first, carve out the obstacle shape with void, then draw boundary there.

```xml
<!-- First draw fluid, then carve out obstacle shape with void, then draw boundary there -->
<setmkfluid mk="0" />
<drawbox>
  <boxfill>solid</boxfill>
  <point x="0" y="-1" z="0.04" />
  <size x="4.0" y="2" z="1.0" />
</drawbox>
<!-- Carve void where obstacle will be -->
<setmkvoid />
<drawcylinder radius="0.1">
  <point x="2.0" y="-1" z="0.5" />
  <point x="2.0" y="1" z="0.5" />
</drawcylinder>
<!-- Draw obstacle as boundary -->
<setmkbound mk="3" />
<drawcylinder radius="0.1">
  <point x="2.0" y="-1" z="0.5" />
  <point x="2.0" y="1" z="0.5" />
</drawcylinder>
```

---

## J7. Flood Fill (fill enclosed region with fluid)

Draw walls first, then flood-fill the interior.

```xml
<setmkbound mk="0" />
<drawbox>
  <boxfill>bottom | left | right</boxfill>
  <point x="0" y="-1" z="0" />
  <size x="3.0" y="2" z="1.0" />
</drawbox>
<setmkfluid mk="0" />
<fillbox x="1.5" y="0" z="0.3">
  <modefill>void</modefill>
  <point x="0.04" y="-1" z="0.04" />
  <size x="2.92" y="2" z="0.5" />
</fillbox>
```

---

## J8. External Mesh (STL obstacle)

```xml
<setmkbound mk="5" />
<drawfilestl file="obstacle.stl" objname="">
  <drawscale x="0.001" y="0.001" z="0.001" />
  <drawmove x="2.0" y="1.0" z="0.5" />
</drawfilestl>
```

---

## J9. Repeated Objects (array of pillars)

```xml
<commands>
  <list name="Pillar">
    <drawcylinder radius="0.05">
      <point x="0" y="-1" z="0" />
      <point x="0" y="1" z="1.0" />
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

---

## J10. Multi-Phase (two fluids)

```xml
<!-- Phase 0: water -->
<setmkfluid mk="0" />
<drawbox>
  <boxfill>solid</boxfill>
  <point x="0" y="-1" z="0.04" />
  <size x="2.0" y="2" z="0.5" />
</drawbox>
<!-- Phase 1: oil (lighter, on top) -->
<setmkfluid mk="1" />
<drawbox>
  <boxfill>solid</boxfill>
  <point x="0" y="-1" z="0.54" />
  <size x="2.0" y="2" z="0.3" />
</drawbox>
```
Each phase needs a corresponding `<phase mkfluid="N">` in `<nnphases>`.

---

## J11. 3D Tank with Obstacle

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

**Note:** In 3D, `pointmin.y ≠ pointmax.y` — both span the real domain. Objects use their actual y coordinates.
