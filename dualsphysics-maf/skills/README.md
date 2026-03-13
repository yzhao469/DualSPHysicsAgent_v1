# skills

Knowledge resources injected into the simulation planning prompt.

## Files in this folder

| File | Main function / logic |
|---|---|
| `dualsphysics-xml/` | Skill bundle used by `SkillsProvider` for progressive disclosure of XML geometry, physics parameters, and probe-placement guidance. |
| `dualsphysics-postprocess/` | Skill bundle for post-processing tools (PartVTK, IsoSurface, ComputeForces, etc.). |

## Subfolder: `dualsphysics-xml/`

| File | Main function / logic |
|---|---|
| `SKILL.md` | Skill entrypoint with metadata plus core GenCase XML structure, domain limits, 2D/3D rules, MK conventions, physics parameters, probe heuristics, and resource index. |
| `drawing-shapes.md` | All shape-creation commands (drawbox, drawsphere, drawcylinder, drawprism, drawbeach, drawextrude, lines, triangles, external geometry) based on XML Guide §2.4.2. |
| `fill-and-modification.md` | Fill operations (fillbox, fillpoint, fillprism), redraw commands for patching holes, freedraw mode, and multi-layer shell creation. |
| `transforms-and-variables.md` | Transformation stack, user variables with expressions and functions, reusable lists, clipping, and debugging commands. |
| `composition-patterns.md` | End-to-end geometry composition examples for common setup patterns (tank, dam-break, slope, STL integration, etc.). |
