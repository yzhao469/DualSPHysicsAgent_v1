import pytest

from mcp_server.tools.generate_points import generate_points_file

pytestmark = pytest.mark.unit


def test_generate_points_file_uses_explicit_points_before_cross_product(tmp_path):
    output = tmp_path / "points.txt"

    generate_points_file(
        str(output),
        probe_xs=[10.0],
        probe_zs=[20.0],
        probe_points=[[1.5, 2.0, 3.5]],
    )

    assert output.read_text(encoding="utf-8") == (
        "POINTSLIST\n1.5 2 3.5\n0 0 0\n1 1 1\n"
    )


def test_generate_points_file_builds_cross_product_grid(tmp_path):
    output = tmp_path / "points.txt"

    generate_points_file(str(output), probe_xs=[0.0, 1.0], probe_zs=[2.0, 3.0], y=1.5)

    assert output.read_text(encoding="utf-8") == (
        "POINTSLIST\n0 1.5 2\n0 0 0\n1 1 1\n\n"
        "POINTSLIST\n0 1.5 3\n0 0 0\n1 1 1\n\n"
        "POINTSLIST\n1 1.5 2\n0 0 0\n1 1 1\n\n"
        "POINTSLIST\n1 1.5 3\n0 0 0\n1 1 1\n"
    )


def test_generate_points_file_requires_input_mode(tmp_path):
    with pytest.raises(ValueError, match="Provide either probe_points or both probe_xs and probe_zs"):
        generate_points_file(str(tmp_path / "points.txt"))
