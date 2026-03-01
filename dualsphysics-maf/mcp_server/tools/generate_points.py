"""Generate a MeasureTool POINTSLIST file from probe coordinates."""
from pathlib import Path


def generate_points_file(
    output_path: str,
    probe_xs: list | None = None,
    probe_zs: list | None = None,
    y: float = 1.0,
    probe_points: list[list[float]] | None = None,
) -> str:
    """Write a MeasureTool POINTSLIST file for the given probe coordinates.

    Two modes:
    1. **Explicit triples** (preferred for general geometry):
       Pass ``probe_points`` as a list of [x, y, z] triples.
    2. **Cross-product** (legacy, for 2D channel cases):
       Pass ``probe_xs`` and ``probe_zs``; one POINTSLIST block is written
       per (x, z) combination at fixed ``y``.

    If both are provided, ``probe_points`` takes precedence.

    Args:
        output_path:  Path to write the points file.
        probe_xs:     List of x coordinates (m) — cross-product mode.
        probe_zs:     List of z coordinates (m) — cross-product mode.
        y:            Fixed y coordinate (m); default 1.0.
        probe_points: List of [x, y, z] triples — explicit mode.

    Returns:
        The path to the written file.
    """
    blocks: list[str] = []

    if probe_points is not None:
        for pt in probe_points:
            x, py, z = pt[0], pt[1], pt[2]
            blocks.append(
                f"POINTSLIST\n{x:.6g} {py:.6g} {z:.6g}\n0 0 0\n1 1 1"
            )
    elif probe_xs is not None and probe_zs is not None:
        for x in probe_xs:
            for z in probe_zs:
                blocks.append(
                    f"POINTSLIST\n{x:.6g} {y:.6g} {z:.6g}\n0 0 0\n1 1 1"
                )
    else:
        raise ValueError("Provide either probe_points or both probe_xs and probe_zs")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text("\n\n".join(blocks) + "\n", encoding="utf-8")
    return output_path
