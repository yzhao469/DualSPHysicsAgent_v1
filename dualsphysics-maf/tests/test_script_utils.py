import pytest

from agents.utils.script_utils import generate_script, parse_script

pytestmark = pytest.mark.unit


# ── generate_script ──────────────────────────────────────────────────

def test_generate_script_includes_default_commands():
    plan = {"params": {"TimeMax": 5.0, "TimeOut": 0.1}}
    script = generate_script(plan, "/tmp/run", "/opt/bin")

    assert "#!/bin/bash" in script
    assert "set -e" in script
    assert "PartVTK_linux64" in script
    assert "+fluid" in script
    assert "+bound" in script


def test_generate_script_uses_bin_dir_variable():
    plan = {"params": {}}
    script = generate_script(plan, "/tmp/run", "/my/custom/bin")

    assert 'BIN_DIR="/my/custom/bin"' in script
    assert '"$BIN_DIR"' in script


# ── parse_script ─────────────────────────────────────────────────────

def test_parse_script_round_trip():
    plan = {"params": {}}
    script = generate_script(plan, "/tmp/run", "/opt/bin")
    commands = parse_script(script)

    assert len(commands) == 2
    assert commands[0].tool_name == "partvtk"
    assert commands[1].tool_name == "partvtk"
    assert "-onlytype:-all,+fluid" in commands[0].args
    assert "-onlytype:-all,+bound" in commands[1].args


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
