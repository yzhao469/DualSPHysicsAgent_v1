# Composition Patterns

Complete geometry examples for common DualSPHysics simulation setups.

---

## J1. Open-top tank (2D)
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

---

## J2. Dam break (2D)
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

---

## J3. Void carving (obstacle inside fluid)
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

---

## J4. Flood fill (fill enclosed region with fluid)
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

---

## J5. Sloped beach / ramp
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

---

## J6. External mesh (STL obstacle)
```xml
<setmkbound mk="5" />
<drawfilestl file="obstacle.stl" objname="">
  <drawscale x="0.001" y="0.001" z="0.001" />
  <drawmove x="2.0" y="1.0" z="0.5" />
</drawfilestl>
```

---

## J7. Repeated objects (array of pillars)
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

---

## J8. Multi-phase (two fluids)
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

---

## J9. 3D tank with obstacle
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
