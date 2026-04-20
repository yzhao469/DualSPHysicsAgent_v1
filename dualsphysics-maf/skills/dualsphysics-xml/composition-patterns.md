# Composition Patterns

Complete geometry examples from real DualSPHysics cases. Study these to understand
how primitives, fill operations, and mk assignments work together.

---

## 2D vs 3D — The Critical Convention

**2D cases** — `pointmin.y == pointmax.y` (tells GenCase this is 2D):
```xml
<pointmin x="-1" y="0" z="-1" />
<pointmax x="4.5" y="0" z="3.5" />
```
Objects still use non-zero y spans (e.g., `y=-1` to `y=1`) — GenCase projects onto the 2D plane.
For 2D: fillbox seed `y=0`, all probe `y=0`.

**3D cases** — `pointmin.y != pointmax.y`:
```xml
<pointmin x="-0.05" y="-0.05" z="-0.05" />
<pointmax x="2" y="1" z="1" />
```
Objects use their actual y coordinates.

---

## P1. 2D Dam Break — simplest case

From `CaseDambreakVal2D_Def.xml`. Fluid column + open-top tank, all in one drawbox each.

```xml
<geometry>
  <definition dp="0.01">
    <pointmin x="-1" y="0" z="-1" />
    <pointmax x="4.5" y="0" z="3.5" />
  </definition>
  <commands>
    <mainlist>
      <setdrawmode mode="full" />
      <setmkfluid mk="0" />
      <drawbox>
        <boxfill>solid</boxfill>
        <point x="0" y="-1" z="0" />
        <size x="1" y="2" z="2" />
      </drawbox>
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

**Techniques:** boxfill with 5 faces for open-top tank. Fluid drawn before boundaries.

---

## P2. 2D Sloshing Tank — fillbox for fluid

From `CaseSloshingMotion_Def.xml`. Closed tank with fluid placed via flood-fill.

```xml
<geometry>
  <definition dp="0.002">
    <pointmin x="-1" y="0" z="-1" />
    <pointmax x="1" y="0" z="1" />
  </definition>
  <commands>
    <mainlist>
      <setshapemode>dp | bound</setshapemode>
      <setdrawmode mode="full" />
      <setmkbound mk="0" />
      <drawbox>
        <boxfill>all</boxfill>
        <point x="-0.45" y="-0.1" z="0" />
        <size x="0.9" y="0.2" z="0.508" />
      </drawbox>
      <setmkfluid mk="0" />
      <fillbox x="0" y="0" z="0.02">
        <modefill>void</modefill>
        <point x="-0.45" y="-0.1" z="0" />
        <size x="0.9" y="0.2" z="0.093" />
      </fillbox>
      <shapeout file="" />
    </mainlist>
  </commands>
</geometry>
```

**Techniques:** Draw closed boundary first, then fillbox to place fluid. Seed point must be
inside the void region. fillbox size limits how high the fluid goes.

---

## P3. 3D Dam Break with Obstacle — void carving

From `CaseDambreak_Def.xml`. 3D tank with a tall obstacle carved using void.

```xml
<geometry>
  <definition dp="0.0085">
    <pointmin x="-0.05" y="-0.05" z="-0.05" />
    <pointmax x="2" y="1" z="1" />
  </definition>
  <commands>
    <mainlist>
      <setshapemode>dp | bound</setshapemode>
      <setdrawmode mode="full" />
      <!-- Fluid -->
      <setmkfluid mk="0" />
      <drawbox>
        <boxfill>solid</boxfill>
        <point x="0" y="0" z="0" />
        <size x="0.4" y="0.67" z="0.3" />
      </drawbox>
      <!-- Tank walls (open top) -->
      <setmkbound mk="0" />
      <drawbox>
        <boxfill>bottom | left | right | front | back</boxfill>
        <point x="0" y="0" z="0" />
        <size x="1.6" y="0.67" z="0.4" />
      </drawbox>
      <shapeout file="Box" />
      <!-- Carve void for obstacle -->
      <setmkvoid />
      <drawbox>
        <boxfill>solid</boxfill>
        <point x="0.9" y="0.24" z="0" />
        <size x="0.12" y="0.12" z="0.45" />
      </drawbox>
      <!-- Draw obstacle as boundary -->
      <setmkbound mk="1" />
      <drawbox>
        <boxfill>top | left | right | front | back</boxfill>
        <point x="0.9" y="0.24" z="0" />
        <size x="0.12" y="0.12" z="0.45" />
      </drawbox>
      <!-- Pressure sensor face -->
      <setmkbound mk="10" />
      <drawbox>
        <boxfill>left</boxfill>
        <point x="0.9" y="0.24" z="0" />
        <size x="0.12" y="0.12" z="0.45" />
      </drawbox>
      <shapeout file="Building" />
    </mainlist>
  </commands>
</geometry>
```

**Techniques:** Void carving — first draw fluid, then erase with `setmkvoid`, then draw boundary
in the same volume. Separate mk values for the impact face (mk=10) vs rest of obstacle (mk=1).
Multiple `shapeout` calls export different parts to separate VTK files.

---

## P4. 2D Beach with drawprism + fillbox

From `CasePistonBeach_REG_Def.xml`. Sloped bottom using drawprism, fluid placed via flood-fill.

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
      <!-- Piston wall -->
      <setmkbound mk="10" />
      <drawbox>
        <boxfill>solid</boxfill>
        <point x="-0.05" y="-1" z="0" />
        <size x="0.05" y="2" z="1.0" />
      </drawbox>
      <!-- Sloped bottom: flat x=-0.5..9, then rising to z=1.0 at x=19 -->
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
      <!-- Flood-fill fluid above the slope -->
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

**Techniques:** `drawprism` with 8 points — first 4 at y=-1, last 4 at y=1. The z-coordinates
vary along x to create the slope. `mask="1 | 2 | 6 | 7"` draws selected faces only.
`fillbox` places fluid in void space above the slope surface.

---

## P5. 3D Wave Tank with Prism — fill + void carving

From `CaseWavemaker_Def.xml`. Two identical prisms: one for solid fluid fill, one for boundary surface.

```xml
<geometry>
  <definition dp="0.02">
    <pointmin x="-0.1" y="-0.05" z="-0.05" />
    <pointmax x="5.1" y="2.1" z="2" />
  </definition>
  <commands>
    <mainlist>
      <setshapemode>real | dp | bound</setshapemode>
      <setdrawmode mode="full" />
      <!-- Step 1: Fill fluid in the tank shape using prism (mask=0 for solid) -->
      <setmkfluid mk="0" />
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
      <!-- Step 2: Carve upper region to set water level -->
      <setmkvoid />
      <drawbox>
        <boxfill>solid</boxfill>
        <point x="0" y="0" z="0.75" />
        <size x="5" y="2" z="1" />
      </drawbox>
      <!-- Step 3: Piston wall -->
      <setmkbound mk="10" />
      <drawbox>
        <boxfill>solid</boxfill>
        <point x="0" y="0" z="0" />
        <size x="0.06" y="2" z="1.5" />
      </drawbox>
      <!-- Step 4: Same prism shape as boundary surface -->
      <setmkbound mk="0" />
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
      <shapeout file="" reset="true" />
    </mainlist>
  </commands>
</geometry>
```

**Techniques:** Dual-prism pattern — first prism fills fluid (mask=0), then void carves
the free surface level, then second prism draws the boundary surface (mask with specific faces).
This gives clean fluid inside a complex tank shape.

---

## P6. 2D Complex Bottom Profile — drawbeach

From `CasePeriodicity_Def.xml`. Multi-segment bottom profile + fillvoidpoint.

```xml
<geometry>
  <definition dp="0.002">
    <pointmin x="-0.1" y="0" z="-0.1" />
    <pointmax x="1" y="0" z="1" />
  </definition>
  <commands>
    <mainlist>
      <setshapemode>actual | bound</setshapemode>
      <setdrawmode mode="full" />
      <!-- Complex bottom profile -->
      <setmkbound mk="0" />
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
      <!-- Internal structure -->
      <drawbeach mask="1|2">
        <point x="0.25" y="1" z="0.01" />
        <point x="0.30" y="1" z="0.01" />
        <point x="0.30" y="1" z="0.04" />
        <point x="0.26" y="1" z="0.08" />
        <point x="0.26" y="1" z="0.34" />
        <point x="0.25" y="1" z="0.34" />
      </drawbeach>
      <!-- Fill voids as boundary -->
      <setmkbound mk="1" />
      <fillvoidpoint x="0.01" y="0" z="-0.005" />
      <fillvoidpoint x="0.26" y="0" z="0.02" />
      <!-- Fill fluid -->
      <setmkfluid mk="0" />
      <fillbox x="0.1" y="0" z="0.1">
        <modefill>void</modefill>
        <point x="0" y="-0.1" z="0" />
        <size x="0.25" y="0.2" z="0.25" />
      </fillbox>
      <fillbox x="0.31" y="0" z="0.01">
        <modefill>void</modefill>
        <point x="0.2" y="-0.1" z="0" />
        <size x="0.6" y="0.2" z="0.03" />
      </fillbox>
      <shapeout file="" />
    </mainlist>
  </commands>
</geometry>
```

**Techniques:** Multiple drawbeach calls for complex profiles. `fillvoidpoint` to fill
thin void regions as boundary. Multiple fillbox calls for fluid in different regions.

---

## P7. Repeated Objects with Lists — bowling pins

From `CaseBowling_Def.xml`. Lists + runlist with auto-incrementing mk.

```xml
<geometry>
  <definition dp="0.01">
    <pointmin x="0" y="1" z="-0.02" />
    <pointmax x="4.3" y="1" z="6" />
  </definition>
  <commands>
    <list name="Block" printcall="false">
      <drawbox>
        <boxfill>solid</boxfill>
        <point x="0" y="0" z="0.0" />
        <size x="0.11" y="2" z="0.1" />
      </drawbox>
      <move x="0.15" y="0" z="0" />
      <move x="0.02" y="0" z="0" />
      <setmknextbound next="true" />
    </list>
    <list name="Row" printcall="false">
      <matrixsave />
      <runlist name="Block" times="5" />
      <matrixload />
      <move x="0" y="0" z="0.1" />
    </list>
    <mainlist>
      <setshapemode>dp | bound</setshapemode>
      <setdrawmode mode="full" />
      <!-- Ramp -->
      <setmkbound mk="0" />
      <drawbeach mask="1|2|5">
        <point x="0" y="2" z="1" />
        <point x="1.5" y="2" z="0" />
        <point x="4.35" y="2" z="0" />
      </drawbeach>
      <!-- Ball -->
      <setmkbound mk="9" />
      <drawcylinder radius="0.25" mask="0">
        <point x="0.3" y="0" z="1.4" />
        <point x="0.3" y="2" z="1.4" />
      </drawcylinder>
      <!-- Array of blocks: 14 rows × 5 blocks -->
      <setmkbound mk="10" />
      <move x="3.4" y="0" z="0.02" />
      <runlist name="Row" times="14" />
      <shapeout file="" reset="true" />
    </mainlist>
  </commands>
</geometry>
```

**Techniques:** Nested lists (Block inside Row). `setmknextbound` auto-increments mk
so each block gets a unique label. `matrixsave`/`matrixload` preserves transform state
between runlist iterations. drawbeach for the ramp, drawcylinder for the ball.

---

## P8. External Mesh — STL slope + blocks

From `CaseWaveRunup_Def.xml`. Import STL files with transforms + flood-fill.

```xml
<geometry>
  <definition dp="0.008">
    <pointmin x="-1" y="0" z="-0.2" />
    <pointmax x="12" y="0.37" z="0.7" />
  </definition>
  <commands>
    <mainlist>
      <setshapemode>dp | actual | bound</setshapemode>
      <setdrawmode mode="solid" />
      <!-- Piston -->
      <setmkbound mk="10" />
      <drawbox cmt="piston">
        <boxfill>solid</boxfill>
        <point x="-0.02" y="-0.01" z="0" />
        <size x="0.02" y="0.39" z="0.55" />
      </drawbox>
      <shapeout file="piston" reset="true" />
      <!-- Flat bottom -->
      <setmkbound mk="0" />
      <drawbox>
        <boxfill>bottom</boxfill>
        <point x="-0.5" y="-0.01" z="0" />
        <size x="7.5" y="0.39" z="0.55" />
      </drawbox>
      <shapeout file="bottom" reset="true" />
      <!-- Import STL slope -->
      <setdrawmode mode="full" />
      <setmkbound mk="40" />
      <drawfilestl file="Slope.stl">
        <drawmove x="5.95" y="0.37" z="0.0" />
        <drawrotate angx="0" angy="0" angz="-90" />
      </drawfilestl>
      <shapeout file="slope" reset="true" />
      <!-- Import STL blocks on the slope -->
      <setmkbound mk="50" />
      <drawfilestl file="Blocks_3D_scaled.stl">
        <drawmove x="5.95" y="0.37" z="0.0" />
        <drawrotate angx="0" angy="0" angz="-90" />
      </drawfilestl>
      <shapeout file="blocks" reset="true" />
      <!-- Fill fluid via flood-fill -->
      <setmkfluid mk="0" />
      <fillbox x="2" y="0.18" z="0.1">
        <modefill>void</modefill>
        <point x="-1" y="-0.01" z="-0.5" />
        <size x="11" y="0.39" z="0.75" />
      </fillbox>
    </mainlist>
  </commands>
</geometry>
```

**Techniques:** `drawfilestl` with `drawmove` and `drawrotate` to position imported meshes.
Different mk values for each imported part. Multiple `shapeout` with `reset="true"` to
export parts separately. Flood-fill for fluid at the end.

---

## P9. 3D Floating Object — mode switching

From `CaseFloating_Def.xml`. Mix of `face` and `full` draw modes.

```xml
<geometry>
  <definition dp="0.1">
    <pointmin x="-1" y="-1" z="-1" />
    <pointmax x="17" y="7" z="6" />
  </definition>
  <commands>
    <mainlist>
      <setshapemode>dp | real | bound</setshapemode>
      <!-- Piston (full mode — solid) -->
      <setdrawmode mode="full" />
      <setmkbound mk="10" />
      <drawbox cmt="Piston">
        <boxfill>solid</boxfill>
        <point x="0.7" y="0" z="0" />
        <size x="0.3" y="6" z="5" />
      </drawbox>
      <!-- Tank walls (face mode — hollow shell for efficiency) -->
      <setdrawmode mode="face" />
      <setmkbound mk="20" />
      <drawbox>
        <boxfill>bottom | right | front | back</boxfill>
        <point x="0" y="0" z="0" />
        <size x="16" y="6" z="6" />
      </drawbox>
      <!-- Floating box (full mode — solid for mass calculation) -->
      <setdrawmode mode="full" />
      <setmkbound mk="50" />
      <drawbox>
        <boxfill>solid</boxfill>
        <point x="10" y="2" z="3" />
        <size x="2" y="2" z="2" />
      </drawbox>
      <!-- Flood-fill fluid -->
      <setmkfluid mk="0" />
      <fillbox x="5" y="2" z="2">
        <modefill>void</modefill>
        <point x="0" y="0" z="0" />
        <size x="16" y="6" z="4" />
      </fillbox>
      <shapeout file="" reset="true" />
    </mainlist>
  </commands>
</geometry>
<!-- REQUIRED: declare floating bodies with mass inside <casedef> -->
<floatings>
    <floating mkbound="50">
        <massbody value="500" />
    </floating>
</floatings>
```

**Techniques:** Mode switching — `face` for large tank walls (fewer particles, more efficient),
`full` for piston and floating object (need solid mass). Floating body gets its own mk (mk=50).
**Critical:** The `<floatings>` section is required after `</geometry>` — without it, mkbound=50
particles are treated as fixed boundaries even though they are in the floating mk range.
`massbody` sets the total mass in kg.

---

## P10. Non-Newtonian Debris Flow — flat channel

From `CaseDebrisFlow2D_Def.xml`. The ground truth non-Newtonian case.

```xml
<geometry>
  <definition dp="0.01">
    <pointmin x="-0.2" y="1" z="-0.2" />
    <pointmax x="8.15" y="1" z="4.15" />
  </definition>
  <commands>
    <mainlist>
      <setshapemode>dp | bound</setshapemode>
      <setdrawmode mode="full" />
      <!-- Debris fluid column -->
      <setmkfluid mk="0" />
      <drawbox>
        <boxfill>solid</boxfill>
        <point x="0" y="0" z="0" />
        <size x="0.5" y="2" z="1.0" />
      </drawbox>
      <!-- Floor -->
      <setmkbound mk="11" />
      <drawbox>
        <boxfill>solid</boxfill>
        <point x="0" y="0" z="0" />
        <size x="4.0" y="2" z="0.04" />
      </drawbox>
      <!-- Left wall -->
      <setmkbound mk="12" />
      <drawbox>
        <boxfill>solid</boxfill>
        <point x="0" y="0" z="0" />
        <size x="0.04" y="2" z="1.25" />
      </drawbox>
      <!-- Right wall -->
      <setmkbound mk="13" />
      <drawbox>
        <boxfill>solid</boxfill>
        <point x="3.96" y="0" z="0" />
        <size x="0.04" y="2" z="1.25" />
      </drawbox>
      <shapeout file="" />
    </mainlist>
  </commands>
</geometry>
```

**Note:** This 2D case uses `pointmin y=1, pointmax y=1` (both equal — valid 2D convention).
Objects span `y=0` to `y=2`. The y-values can be any constant as long as pointmin.y == pointmax.y.
Separate mk values per wall for force measurement.

---

## P11. VTK Hull Import — inlet/outlet setup

From `CaseCurrentHull_Def.xml`. Import VTK hull + multi-mk inlet/outlet.

```xml
<geometry>
  <definition dp="0.01">
    <pointmin x="-0.3" y="-1" z="-1" />
    <pointmax x="2.1" y="1" z="1" />
  </definition>
  <commands>
    <mainlist>
      <setshapemode>actual | bound</setshapemode>
      <setdrawmode mode="full" />
      <!-- Inlet boundary (mkfluid=1) -->
      <setmkfluid mk="1" />
      <drawbox>
        <boxfill>left</boxfill>
        <point x="-0.2" y="-0.5" z="0" />
        <size x="2.2" y="1" z="0.4" />
      </drawbox>
      <!-- Outlet boundary (mkfluid=2) -->
      <setmkfluid mk="2" />
      <drawbox>
        <boxfill>right</boxfill>
        <point x="-0.2" y="-0.5" z="0" />
        <size x="2.2" y="1" z="0.4" />
      </drawbox>
      <!-- Tank walls -->
      <setmkbound mk="0" />
      <drawbox>
        <boxfill>bottom | front | back</boxfill>
        <point x="-2" y="-0.5" z="0" />
        <size x="5" y="1" z="0.4" />
      </drawbox>
      <!-- Import hull geometry -->
      <setmkbound mk="20" />
      <drawfilevtk file="Hull.vtk">
        <drawmove x="0.75" y="0" z="0.13" />
      </drawfilevtk>
      <!-- Fill fluid -->
      <setmkfluid mk="0" />
      <setboxlimitmode mode="full" />
      <fillbox x="0.1" y="0" z="0.1">
        <modefill>void</modefill>
        <point x="-2" y="-1" z="-1" />
        <size x="5" y="2" z="1.2" />
      </fillbox>
      <shapeout file="" />
    </mainlist>
  </commands>
</geometry>
```

**Techniques:** `mkfluid=1` and `mkfluid=2` for inlet/outlet zones (used by the inlet/outlet
special feature). `drawfilevtk` imports the hull. `setboxlimitmode mode="full"` ensures
fill extends to box edges. Fluid fill (mk=0) placed last.
