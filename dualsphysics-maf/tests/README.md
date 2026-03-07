# tests

Pytest suite for `dualsphysics-maf`.

## Files in this folder

| File | Main function / logic |
|---|---|
| `README.md` | Documents the pytest layout and current bootstrap scope for the `tests` folder. |
| `conftest.py` | Shared pytest fixtures for representative case XML and MeasureTool-style CSV test data. |
| `test_generate_points.py` | Unit tests for POINTSLIST file generation in explicit-point and x-z grid modes. |
| `test_metrics.py` | Unit tests for CSV metric calculation behavior, including interpolation and error handling. |
| `test_schemas.py` | Unit tests for the core Pydantic/dataclass workflow schema models. |
| `test_skill_loader.py` | Unit tests for skill markdown loading order and module-level caching behavior. |
| `test_xml_modifier.py` | Unit tests for non-geometry XML parameter updates and output file creation. |
| `test_xml_utils.py` | Unit tests for preprocessing non-standard DualSPHysics XML into parser-safe XML. |

## Current scope

- `tests/` currently focuses on fast unit coverage for pure helpers and local file transforms.
- Workflow, MCP server, LLM, and external-binary paths are intentionally left for future mocked integration tests.
