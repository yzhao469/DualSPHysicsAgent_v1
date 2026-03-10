# Transforms, Variables, Reusable Lists & Clipping

---

## Transforms

Transforms apply to all subsequent drawing commands until reset.

### Basic transforms
```xml
<move x="DX" y="DY" z="DZ" />
<scale x="SX" y="SY" z="SZ" />
<rotate ang="45" x="0" y="0" z="1" />         <!-- rotate 45° around vector (0,0,1) -->
<rotateline ang="45">                          <!-- rotate around arbitrary axis -->
  <point x="0" y="0" z="0" />
  <point x="1" y="0" z="0" />
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

Variables can reference each other:
```xml
<newvar SizeX="0.25" SizeZ="(Dp+2)*2.8" dpd2="Dp/2" />
```

### Using variables
Numeric variables use `#` prefix:
```xml
<drawbox>
  <boxfill>solid</boxfill>
  <point x="0" y="-1" z="0" />
  <size x="#TankLen" y="2" z="#TankH" />
</drawbox>
```

Text variables use `$[name]`:
```xml
<shapeout file="$[CaseName]_output" />
```

### Modifying variables
```xml
<setvar SizeZ="SizeX+Cte1*Cte2" />
<setvarstr Text3="[Text1]_modified" />
```

### Built-in auto-constants
Available automatically — do not redefine:
- `Dp` — particle spacing
- `Gravity_x`, `Gravity_y`, `Gravity_z` — gravity components
- `Rhop0` — reference fluid density
- `PosMin_x`, `PosMin_y`, `PosMin_z` — domain min
- `PosMax_x`, `PosMax_y`, `PosMax_z` — domain max
- `Data2D`, `Data2DPosy` — 2D mode flag and y-position
- `H`, `MassBound`, `MassFluid` — derived constants
- `CaseName`

### Predefinition section
Variables can be defined before `<geometry>` to parameterise dp and domain limits:
```xml
<geometry>
  <predefinition>
    <newvar TankLen="4.0" Margin="0.5" />
  </predefinition>
  <definition dp="#Dp">
    <pointmin x="-#Margin" y="0" z="-#Margin" />
    <pointmax x="#TankLen+#Margin" y="0" z="3" />
  </definition>
  ...
</geometry>
```

### Math functions available in expressions
`pi()`, `e()`, `int()`, `float()`, `abs()`, `floor()`, `ceil()`, `round()`,
`min()`, `max()`, `sqrt()`, `exp()`, `log()`, `log10()`, `pow()`,
`sin()`, `cos()`, `tan()`, `sindg()`, `cosdg()`, `tandg()` (degree versions),
`asin()`, `acos()`, `atan()`, `atan2()`,
`eval(condition, v1, v2)` (ternary),
`wavelength(gravity, depth, period)`,
`random()`, `rand(a)`, `rand(a,b)`, `randint(a,b)`

### Operators
- Math: `+`, `-`, `*`, `/`
- Comparison: `==`, `!=`, `<`, `>`, `<=`, `>=`
- Logical: `!` (not), `||` (or), `@@` (and)

### Export variables to DualSPHysics
```xml
<exportvar vars="-all,Dp,Rhop0,PosMax*" />
```

---

## Reusable Lists

Define command groups and call them multiple times.

### Defining a list
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
    <!-- ... -->
  </mainlist>
</commands>
```

### Running a list
```xml
<runlist name="WallSegment" />         <!-- run once -->
<runlist name="WallSegment" times="5" />  <!-- run 5 times -->
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

### Pattern — auto-increment mk with repeated list
```xml
<!-- From CaseBowling_Def.xml -->
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
<printf text="Tank length = #TankLen#" />
<printf if="Dp<0.01" text="Warning: dp=#Dp# is very small" />
<abort if="Dp<0.001" text="dp too small, aborting" />
<debugout />
<cellsout file="cells_bound5" mkbound="5" />
<pointsmkout file="points" />
```
