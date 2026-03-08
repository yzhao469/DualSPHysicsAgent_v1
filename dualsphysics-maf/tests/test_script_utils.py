import pytest

from agents.utils.script_utils import generate_script, parse_script

pytestmark = pytest.mark.unit


# ── generate_script ──────────────────────────────────────────────────

def test_generate_script_includes_default_commands():
    plan = {"params": {"TimeMax": 5.0, "TimeOut": 0.1}, "probe_points": []}
    script = generate_script(plan, "/tmp/run", "/opt/bin")

    assert "#!/bin/bash" in script
    assert "set -e" in script
    assert "PartVTK_linux64" in script
    assert "+fluid" in script
    assert "+bound" in script


def test_generate_script_includes_measuretool_when_probes_exist():
    plan = {"params": {}, "probe_points": [[0.1, 1.0, 0.2]]}
    script = generate_script(plan, "/tmp/run", "/opt/bin")

    assert "MeasureTool_linux64" in script
    assert "PointsMeasure" in script


def test_generate_script_skips_measuretool_when_no_probes():
    plan = {"params": {}, "probe_points": []}
    script = generate_script(plan, "/tmp/run", "/opt/bin")

    assert "MeasureTool" not in script


def test_generate_script_uses_bin_dir_variable():
    plan = {"params": {}, "probe_points": []}
    script = generate_script(plan, "/tmp/run", "/my/custom/bin")

    assert 'BIN_DIR="/my/custom/bin"' in script
    assert '"$BIN_DIR"' in script


# ── parse_script ─────────────────────────────────────────────────────

def test_parse_script_extracts_commands():
    plan = {"params": {}, "probe_points": [[0.1, 1.0, 0.2]]}
    script = generate_script(plan, "/tmp/run", "/opt/bin")
    commands = parse_script(script)

    tool_names = [c.tool_name for c in commands]
    assert "partvtk" in tool_names
    assert "measuretool" in tool_names


def test_parse_script_round_trip_no_probes():
    plan = {"params": {}, "probe_points": []}
    script = generate_script(plan, "/tmp/run", "/opt/bin")
    commands = parse_script(script)

    assert len(commands) == 2
    assert commands[0].tool_name == "partvtk"
    assert commands[1].tool_name == "partvtk"
    assert "-onlytype:-all,+fluid" in commands[0].args
    assert "-onlytype:-all,+bound" in commands[1].args


def test_parse_script_round_trip_with_probes():
    plan = {"params": {}, "probe_points": [[0.1, 1.0, 0.2]]}
    script = generate_script(plan, "/tmp/run", "/opt/bin")
    commands = parse_script(script)

    assert len(commands) == 3
    assert commands[2].tool_name == "measuretool"


def test_parse_script_ignores_boilerplate():
    script = """\
#!/bin/bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="/opt/bin"
export LD_LIBRARY_PATH="$BIN_DIR:$LD_LIBRARY_PATH"

"""
    commands = parse_script(script)
    assert commands == []


def test_parse_script_handles_empty_script():
    assert parse_script("") == []
    assert parse_script("\n\n") == []


def test_parse_script_preserves_comments():
    script = """\
#!/bin/bash
set -e
BIN_DIR="/opt/bin"
export LD_LIBRARY_PATH="$BIN_DIR"

# --- Fluid particles ---
# Export all fluid data
"$BIN_DIR"/PartVTK_linux64 -dirin out/data -savevtk out/PartFluid -onlytype:-all,+fluid
"""
    commands = parse_script(script)
    assert len(commands) == 1
    assert "Fluid particles" in commands[0].comment
    assert "Export all fluid data" in commands[0].comment
