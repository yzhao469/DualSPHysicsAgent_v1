# skills

Knowledge resources injected into the simulation planning prompt.

## Files in this folder

| File | Main function / logic |
|---|---|
| `dualsphysics-xml/` | Skill bundle used by `SkillsProvider` for progressive disclosure of XML geometry, physics parameters, and probe-placement guidance. |

## Subfolder: `dualsphysics-xml/`

| File | Main function / logic |
|---|---|
| `SKILL.md` | Skill entrypoint with metadata plus core GenCase XML structure, MK conventions, parameter heuristics, and resource index. |
| `drawing-primitives.md` | Detailed drawing/fill command reference (`drawbox`, `drawcylinder`, `fillbox`, etc.) for geometry construction. |
| `transforms-and-advanced.md` | Transform stack, variables, reusable lists, and advanced drawing mode guidance. |
| `composition-patterns.md` | End-to-end geometry composition examples for common setup patterns (tank, dam-break, slope, STL integration, etc.). |
