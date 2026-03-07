"""Helpers for keeping workflow plan state aligned with case files."""

import xml.etree.ElementTree as ET
from pathlib import Path

from mcp_server.tools._xml_utils import preprocess_xml


def extract_plan_update(case_xml: str) -> dict[str, object]:
    """Extract the current geometry and physics params from a case XML file."""
    raw = Path(case_xml).read_text(encoding="utf-8", errors="replace")
    root = ET.fromstring(preprocess_xml(raw))

    geometry = root.find("casedef/geometry")
    phase = root.find("execution/special/nnphases/phase[@mkfluid='0']")
    if geometry is None or phase is None:
        raise ValueError(f"Could not extract geometry/phase data from {case_xml}")

    return {
        "geometry_xml": ET.tostring(geometry, encoding="unicode"),
        "params": {
            "gravity_z": _read_required_attr(root, "casedef/constantsdef/gravity", "z", float),
            "rhop0": _read_required_attr(root, "casedef/constantsdef/rhop0", "value", float),
            "coefh": _read_required_attr(root, "casedef/constantsdef/coefh", "value", float),
            "cflnumber": _read_required_attr(root, "casedef/constantsdef/cflnumber", "value", float),
            "phase_rhop": _read_required_attr(phase, "rhop", "value", float),
            "visco_nn": _read_required_attr(phase, "visco", "value", float),
            "tau_yield": _read_required_attr(phase, "tau_yield", "value", float),
            "HBP_m": _read_required_attr(phase, "HBP_m", "value", float),
            "HBP_n": _read_required_attr(phase, "HBP_n", "value", float),
            "Visco": _read_exec_param(root, "Visco", float),
            "DensityDT": _read_exec_param(root, "DensityDT", lambda value: int(float(value))),
            "DensityDTvalue": _read_exec_param(root, "DensityDTvalue", float),
            "TimeMax": _read_exec_param(root, "TimeMax", float),
            "TimeOut": _read_exec_param(root, "TimeOut", float),
        },
    }


def _read_exec_param(root: ET.Element, key: str, caster) -> float | int:
    """Read execution/parameters/parameter[@key=...] value as a typed scalar."""
    return _read_required_attr(root, f"execution/parameters/parameter[@key='{key}']", "value", caster)


def _read_required_attr(node: ET.Element, path: str, attr: str, caster):
    """Read a required attribute from the selected XML element."""
    element = node.find(path)
    if element is None:
        raise ValueError(f"Missing XML element: {path}")

    raw_value = element.get(attr)
    if raw_value is None:
        raise ValueError(f"Missing XML attribute {attr!r} on {path}")
    return caster(raw_value)
