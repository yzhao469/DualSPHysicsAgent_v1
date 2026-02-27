"""Generate a MeasureTool POINTSLIST file from probe coordinates."""
from pathlib import Path


def generate_points_file(
    output_path: str,
    probe_xs: list,
    probe_zs: list,
    y: float = 1.0,
) -> str:
    """Write a MeasureTool POINTSLIST file for the given probe coordinates.

    One POINTSLIST block is written per (x, z) combination (all z values for
    each x, ordered x-major). The y coordinate is fixed for the 2D case.

    Args:
        output_path: Path to write the points file.
        probe_xs:    List of x coordinates (m).
        probe_zs:    List of z coordinates (m); each x gets every z value.
        y:           Fixed y coordinate (m); default 1.0 (centre of 2D domain).

    Returns:
        The path to the written file.
    """
    blocks = []
    for x in probe_xs:
        for z in probe_zs:
            blocks.append(
                f"POINTSLIST\n{x:.6g} {y:.6g} {z:.6g}\n0 0 0\n1 1 1"
            )

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text("\n\n".join(blocks) + "\n", encoding="utf-8")
    return output_path
