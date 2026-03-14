"""Shared build helpers for executors that re-run gencase + visualization."""

import json
import logging

from agent_framework import MCPStdioTool

from agents.tools.visualize_geometry import visualize_geometry

logger = logging.getLogger(__name__)


async def rebuild_gencase_viz(mcp: MCPStdioTool, run_dir: str) -> None:
    """Re-run GenCase and regenerate visualization.

    Assumes the Case_Def.xml in *run_dir* has already been updated.
    """
    # GenCase
    logger.info(">>> run_gencase (rebuild)")
    r = await mcp.call_tool(
        "run_gencase",
        xml_path=f"{run_dir}/Case_Def",
        output_dir=f"{run_dir}/out",
    )
    result = json.loads(r) if isinstance(r, str) else r
    if result.get("returncode", -1) != 0:
        raise RuntimeError(f"run_gencase failed: {result.get('stderr', r)}")
    logger.info("run_gencase OK")

    # Visualize
    logger.info(">>> visualize_geometry (rebuild)")
    viz_result = visualize_geometry(f"{run_dir}/out")
    logger.info("visualize_geometry: %s", viz_result)
