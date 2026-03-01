# XML format templates

This folder contains XML snippets and templates used to configure DualSPHysics cases.

## Main files

- `CaseTemplate.xml`  
  Base XML case template.
- `GenCase_Bathymetry.csv`  
  Example CSV file used by XML operations that read bathymetry/input points.
- `_FmtXML__Parameters.xml`  
  Common execution and parameter definitions.

## Feature-specific templates

Files with the `_FmtXML_*.xml` naming pattern provide feature-focused XML examples:

- `AccInput`, `BoundCorr`, `Chrono`, `Damping`, `Gauges`
- `InOut`, `Initialize`, `SaveDt`, `Shifting`, `TimeOut`
- `MLPistons`, `RelaxationZones`, `WavePaddles`, `WavePaddlesAwas`, `WavePaddlesSolitary`
- `MoorDyn`, `MphaseNNewtonian`

Use these files as reference blocks when building or extending case XML definitions.
