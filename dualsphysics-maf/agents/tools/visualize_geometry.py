"""Geometry visualization — renders GenCase VTK output to a PNG screenshot
using pyvista (offscreen), then opens the image for user inspection."""

import platform
import subprocess
from pathlib import Path


def _is_wsl() -> bool:
    """Detect if running inside WSL."""
    try:
        return "microsoft" in platform.uname().release.lower()
    except Exception:
        return False


def _find_vtk_file(vtk_dir: str) -> Path | None:
    """Find the main VTK file in GenCase output directory.

    Prefers _Actual.vtk (full particle config), falls back to _Dp.vtk,
    then any .vtk file.
    """
    d = Path(vtk_dir)
    for pattern in ["*_Actual.vtk", "*_Dp.vtk"]:
        matches = sorted(d.glob(pattern))
        if matches:
            return matches[0]
    matches = sorted(d.glob("*.vtk"))
    return matches[0] if matches else None


def _open_image(png_path: str) -> None:
    """Open a PNG image with the system viewer."""
    if _is_wsl():
        try:
            win_path = subprocess.check_output(
                ["wslpath", "-w", png_path], text=True
            ).strip()
            subprocess.Popen(
                ["cmd.exe", "/c", "start", "", win_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            pass  # Fall through — user can open the file manually
    else:
        # Try xdg-open (Linux) or open (macOS)
        for opener in ["xdg-open", "open"]:
            try:
                subprocess.Popen(
                    [opener, png_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                break
            except FileNotFoundError:
                continue


def visualize_geometry(vtk_dir: str) -> str:
    """Render GenCase VTK output to a PNG image for visual inspection.

    Uses pyvista in offscreen mode to render the particle configuration,
    colored by MK (material kind). The PNG is saved next to the VTK files
    and opened with the system image viewer.

    Args:
        vtk_dir: Directory containing GenCase VTK output files.

    Returns:
        A confirmation message or error string.
    """
    vtk_file = _find_vtk_file(vtk_dir)
    if vtk_file is None:
        return f"ERROR: no VTK files found in {vtk_dir}"

    png_path = vtk_file.with_suffix(".png")

    try:
        import pyvista as pv

        pv.OFF_SCREEN = True

        mesh = pv.read(str(vtk_file))

        plotter = pv.Plotter(off_screen=True, window_size=[1600, 900])

        # Color by Mk (material kind) if available, otherwise solid color
        if "Mk" in mesh.point_data:
            plotter.add_mesh(
                mesh,
                scalars="Mk",
                cmap="tab10",
                point_size=3,
                render_points_as_spheres=True,
                show_scalar_bar=True,
                scalar_bar_args={"title": "Mk (material)"},
            )
        else:
            plotter.add_mesh(
                mesh,
                color="steelblue",
                point_size=3,
                render_points_as_spheres=True,
            )

        plotter.add_axes()
        plotter.view_xz()  # Side view (good for 2D channel flows)
        plotter.screenshot(str(png_path))
        plotter.close()

    except Exception as e:
        return f"ERROR: pyvista rendering failed: {e}\nVTK file is at: {vtk_file}"

    # Open the PNG for the user
    _open_image(str(png_path))

    return (
        f"Rendered {vtk_file.name} → {png_path.name}\n"
        f"Path: {png_path}\n"
        f"The image should be open. Inspect the particle configuration, "
        f"then approve or request changes."
    )
