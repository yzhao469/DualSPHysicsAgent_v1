# mcp_server

FastMCP server package exposing simulation-control tools to the agent workflow.

## Files in this folder

| File | Main function / logic |
|---|---|
| `__init__.py` | Package marker for the MCP server module. |
| `config.py` | Centralized paths and timeout constants for binaries, run directories, case files, and ground-truth data. |
| `server.py` | Registers FastMCP tools and exposes them over stdio for XML editing, geometry setup, run execution, and metrics. |

## Subfolder

- [`tools/README.md`](tools/README.md)
