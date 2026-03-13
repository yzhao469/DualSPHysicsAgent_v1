# Transforms, Variables, Reusable Lists, Clipping & Debugging

Control flow, parameterisation, and advanced geometry manipulation.
Based on the DualSPHysics XML Guide v5.0 §2.4.2.

---

## Transformations

Transforms apply to all subsequent drawing commands until reset.

| Command | Description |
|---------|-------------|
| `<move>` | Displacement applied to the transformation matrix |
| `<scale>` | Scaling applied to the matrix |
| `<rotate>` | Rotate around a vector by an angle |
| `<rotateline>` | Rotate around an arbitrary axis defined by two points |
| `<matrixreset>` | Reset transform to identity matrix |
| `<matrixsave>` | Push current transform onto stack |
| `<matrixload>` | Pop and restore last saved transform |

### Basic transforms
```xml
<move x="DX" y="DY" z="DZ" />
<scale x="SX" y="SY" z="SZ" />
<rotate ang="45" x="0" y="0" z="1" />         <!-- rotate 45° around Z-axis -->
<rotateline ang="45">                          <!-- rotate around arbitrary axis -->
  <point x="0" y="0" z="0" />
  <point x="1" y="1" z="-1" />
</rotateline>
```

### Matrix stack
```xml
<matrixsave />         <!-- push current transform onto stack -->
<matrixload />         <!-- pop and restore last saved transform -->
<matrixreset />        <!-- reset transform to identity -->
```

**Usage pattern — place an object at a transformed position, then restore:**
```xml
<matrixsave />
<move x="2" y="0" z="0" />
<rotate ang="45" x="0" y="0" z="1" />
<drawbox>
  <boxfill>solid</boxfill>
  <point x="0" y="-1" z="0" />
  <size x="1" y="2" z="0.5" />
</drawbox>
<matrixload />
```

**Transformation sequence example:**
```xml
<drawbox ... />
<move x="0.5" y="0" z="0" />
<drawbox ... />
<scale x="2" y="1.5" z="0.5" />
<drawbox ... />
<rotate x="0" y="0" z="1" ang="45" />
<drawbox ... />
```

---

## Variables

GenCase supports user-defined variables for parameterised geometry.

### Defining variables
```xml
<!-- Numeric variables (double precision) -->
<newvar TankLen="4.0" TankH="1.5" WallThk="0.04" />

<!-- Constants (cannot be changed later) -->
<newvarcte Pi="3.14159265" />

<!-- String variables -->
<newvarstr CaseName="MyCase" />
<newvarstrcte FixedName="Output" />
```

Variables can reference each other and use expressions:
```xml
<newvar SizeX="0.25" SizeZ="(Dp+2)*2.8" dpd2="Dp/2" />
<newvarcte cte1="1.0" cte2="var1+var2/size" />
```

The `_rem` attribute adds comments, `_print="1"` shows values on screen:
```xml
<newvar size="0.4" _rem="Defines size" _print="1" />
```

Values `true` and `false` are stored as 1 and 0.

### Predefinition section
Variables defined in `<predefinition>` can parametrise dp and domain limits:
```xml
<geometry>
  <predefinition>
    <newvarcte sizex="1.2" _rem="size domain" />
    <newvarcte sizez="sizex*0.8" _rem="size domain" />
    <newvarcte Dp="sizex/100" _rem="particle size" />
    <newvarstr filestl="cube.stl" />
  </predefinition>
  <definition dp="#Dp">
    <pointmin x="#-sizex/2" y="0" z="0" />
    <pointmax x="#sizex" y="0" z="#sizez" />
  </definition>
  <commands>
    <mainlist>
      <newvarcte posx1="-sizex*0.5" />
      <!-- ... -->
    </mainlist>
  </commands>
</geometry>
```

### Using variables in commands

**Numeric variables or expressions** use `#` prefix:
```xml
<drawbox>
  <boxfill>solid</boxfill>
  <point x="0" y="-1" z="0" />
  <size x="#TankLen" y="2" z="#TankH" />
</drawbox>
<move x="#inix" y="0" z="#iniz" />
<drawfilestl file="$[filestl]" if="Dp<=0.1" />
<runlist name="DrawShape" times="#10/inix" />
```

**Text variables** use `$[name]`:
```xml
<shapeout file="$[CaseName]_output" />
```

**Conditional execution** — the `if` attribute is recognised by all drawing commands:
```xml
<drawfilestl file="$[filestl]" if="Dp<=0.1" />
<printf if="Dp<0.01" text="Warning: dp=#Dp# is very small" />
```

Variables can be used in these XML sections: `<geometry>`, `<initials>`, `<floatings>`,
`<properties>`, `<motion>`, `<normals>`, `<special>`, and `<parameters>`.

```xml
<initials>
  <velocity mkfluid="1" x="0" y="0" z="#-Gravity_z*2" />
</initials>
<floatings>
  <floating mkbound="2">
    <center x="#inix" y="0" z="#iniz" />
  </floating>
</floatings>
```

### Modifying variables
```xml
<setvar SizeZ="SizeX+Cte1*Cte2" _rem="Changes value of SizeZ" />
<setvar dpd2="dpd2+Dp" SizeX="SizeX*dpd2" />
<setvarstr Text3="[Text1]" Text4="BBBB" _rem="Modify values" />
```

### Built-in auto-constants
Available automatically — do not redefine:

| Variable(s) | Description |
|---|---|
| `Dp` | Inter-particle distance (loaded after `<predefinition>`) |
| `Gravity_x`, `Gravity_y`, `Gravity_z` | Gravity components (loaded before `<predefinition>`) |
| `Rhop0` | Reference fluid density (loaded before `<predefinition>`) |
| `PosMin_x`, `PosMin_y`, `PosMin_z` | Domain minimum |
| `PosMax_x`, `PosMax_y`, `PosMax_z` | Domain maximum |
| `Data2D`, `Data2DPosy` | 2D mode flag and y-position |
| `H`, `MassBound`, `MassFluid` | Derived constants (created before drawing commands) |
| `CaseName` | Name of the case |

### Expressions and functions

| Category | Operators / Functions |
|---|---|
| **Math operators** | `+`, `-`, `*`, `/` |
| **Comparison** | `==`, `!=`, `<`, `>`, `<=`, `>=` |
| **Logical** | `!` (not), `\|\|` (or), `@@` (and) |
| **Constants** | `pi()`, `e()` |
| **Casting** | `int(a)`, `float(a)` |
| **Rounding** | `abs(a)`, `floor(a)`, `ceil(a)`, `round(a)`, `fmod(a,b)`, `fmodr(a,b)` |
| **Min / Max** | `min(a,b)`, `min(a,b,c)`, `max(a,b)`, `max(a,b,c)` |
| **Power / Log** | `sqrt(a)`, `exp(a)`, `log(a)`, `log10(a)`, `pow(a,b)` |
| **Trig (radians)** | `sin(r)`, `cos(r)`, `tan(r)` |
| **Trig (degrees)** | `sindg(d)`, `cosdg(d)`, `tandg(d)` |
| **Hyperbolic** | `sinh(a)`, `cosh(a)`, `tanh(a)` |
| **Inverse trig** | `asin(a)`, `acos(a)`, `atan(a)`, `atan2(a,b)` |
| **Random** | `randinit(seed)`, `random()`, `rand(a)`, `rand(a,b)`, `randint(a,b)` |
| **Conditional** | `eval(condition, v1, v2)` — returns v1 when true, v2 otherwise |
| **Wave** | `wavelength(gravity, depth, waveperiod)` — returns wave length |

### Export variables to DualSPHysics
```xml
<exportvar vars="file,num1,sizez" />
<exportvar vars="-all,Dp,Rhop0,PosMax*" />
```

Without `<exportvar>`, all user-defined variables are exported to `<execution><uservars>`.
With it, only the specified variables are exported.

---

## Reusable Lists

Define command groups and call them multiple times.

### Defining and running a list
```xml
<commands>
  <list name="WallSegment">
    <drawbox>
      <boxfill>solid</boxfill>
      <point x="0" y="-1" z="0" />
      <size x="0.04" y="2" z="1.5" />
    </drawbox>
  </list>
  <mainlist>
    <runlist name="WallSegment" />         <!-- run once -->
    <runlist name="WallSegment" times="5" />  <!-- run 5 times -->
  </mainlist>
</commands>
```

### Pattern — repeated objects with transform reset
```xml
<list name="Pillar">
  <drawcylinder radius="0.05">
    <point x="0" y="-1" z="0" />
    <point x="0" y="1" z="1.0" />
  </drawcylinder>
</list>
<mainlist>
  <setmkbound mk="10" />
  <move x="1.0" y="0" z="0" />
  <runlist name="Pillar" />
  <matrixreset />
  <move x="2.0" y="0" z="0" />
  <runlist name="Pillar" />
  <matrixreset />
</mainlist>
```

### Pattern — nested lists with auto-increment mk
```xml
<list name="Block" printcall="false">
  <drawbox>
    <boxfill>solid</boxfill>
    <point x="0" y="0" z="0" />
    <size x="0.11" y="2" z="0.1" />
  </drawbox>
  <move x="0.15" y="0" z="0" />
  <setmknextbound next="true" />   <!-- increment mk each time -->
</list>
<list name="Row" printcall="false">
  <matrixsave />
  <runlist name="Block" times="5" />
  <matrixload />
  <move x="0" y="0" z="0.1" />
</list>
<mainlist>
  <setmkbound mk="10" />
  <move x="3.4" y="0" z="0.02" />
  <runlist name="Row" times="14" />
</mainlist>
```

### Pattern — composing structures from sub-lists
```xml
<list name="BoxList">
  <drawbox>
    <boxfill>all</boxfill>
    <point x="0" y="0" z="0" />
    <size x="1" y="1" z="0.3" />
  </drawbox>
</list>
<list name="CylinderList">
  <drawcylinder radius="0.3">
    <point x="0" y="0" z="0" />
    <point x="0" y="0" z="1.2" />
  </drawcylinder>
</list>
<list name="StructureList">
  <matrixsave />
  <runlist name="BoxList" />
  <move x="0.5" y="0.5" z="0.3" />
  <runlist name="CylinderList" />
  <move x="-0.5" y="-0.5" z="1.2" />
  <runlist name="BoxList" />
  <matrixload />
</list>
<mainlist>
  <setmkbound mk="0" />
  <runlist name="StructureList" />
  <move x="1.5" y="0" z="0" />
  <setmkbound mk="1" />
  <runlist name="StructureList" />
</mainlist>
```

---

## Clipping

Restrict subsequent drawing commands to a region.

### Clip by plane
```xml
<!-- Three-point plane definition -->
<clipplane>
  <point1 x="0" y="0" z="0" />
  <point2 x="1" y="0" z="0" />
  <point3 x="1" y="0" z="1" />
</clipplane>

<!-- Point + normal vector -->
<clipplane>
  <point x="0" y="0" z="0" />
  <vector x="0" y="0" z="1" />
</clipplane>
```

### Clip by box
```xml
<clipbox>
  <point x="0" y="0" z="0" />
  <size x="1" y="2" z="3" />
</clipbox>

<!-- With face selection -->
<clipbox>
  <boxfaces>bottom | left | right | front | back</boxfaces>
  <point x="0" y="0" z="0" />
  <size x="1" y="2" z="3" />
</clipbox>
```

### Reset
```xml
<clipreset />   <!-- Remove all clipping restrictions -->
<clipdomain />  <!-- Clip to domain bounds -->
```

---

## Debugging & Output

```xml
<!-- Print variable values -->
<printf text="Tank length = #TankLen#" />
<printf text="Sum of #sx# and #sz# is #sx+sz#" />
<printf if="Dp<0.01" text="Warning: dp=#Dp# is very small" />

<!-- Abort execution conditionally -->
<abort if="Dp<0.001" text="dp too small, aborting" />

<!-- Debug and diagnostic output -->
<debugout />
<cellsout file="cells_bound5" mkbound="5" />
<pointsmkout file="points" />
```
