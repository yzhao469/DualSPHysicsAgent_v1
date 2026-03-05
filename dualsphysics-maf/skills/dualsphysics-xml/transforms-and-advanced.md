# Transforms, Variables, Reusable Lists & Drawing Modes

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
