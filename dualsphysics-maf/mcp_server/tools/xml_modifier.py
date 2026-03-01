"""XML modifier for DualSPHysics case files.

Modifies physics and execution parameters (constantsdef, nnphases,
execution/parameters).  Use ``set_geometry`` for geometry changes.
"""
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

from ._xml_utils import preprocess_xml


def modify_xml(
    base_xml: str,
    output_xml: str,
    # ---- constantsdef ----
    gravity_z: Optional[float] = None,
    rhop0: Optional[float] = None,
    coefh: Optional[float] = None,
    cflnumber: Optional[float] = None,
    # ---- non-Newtonian phase (mkfluid=0) ----
    phase_rhop: Optional[float] = None,
    visco_nn: Optional[float] = None,
    tau_yield: Optional[float] = None,
    HBP_m: Optional[float] = None,
    HBP_n: Optional[float] = None,
    # ---- execution/parameters ----
    Visco: Optional[float] = None,
    DensityDT: Optional[int] = None,
    DensityDTvalue: Optional[float] = None,
    TimeMax: Optional[float] = None,
    TimeOut: Optional[float] = None,
) -> str:
    """Copy base_xml to output_xml and apply only the provided physics params.

    Geometry is NOT handled here — use set_geometry instead.

    Returns the path to the output XML file.
    """
    # Read and preprocess the source XML
    with open(base_xml, "r", encoding="utf-8", errors="replace") as fh:
        raw = fh.read()

    fixed = preprocess_xml(raw)
    root = ET.fromstring(fixed)

    # --- casedef/constantsdef ---
    if gravity_z is not None:
        el = root.find("casedef/constantsdef/gravity")
        if el is not None:
            el.set("z", str(gravity_z))

    if rhop0 is not None:
        el = root.find("casedef/constantsdef/rhop0")
        if el is not None:
            el.set("value", str(rhop0))

    if coefh is not None:
        el = root.find("casedef/constantsdef/coefh")
        if el is not None:
            el.set("value", str(coefh))

    if cflnumber is not None:
        el = root.find("casedef/constantsdef/cflnumber")
        if el is not None:
            el.set("value", str(cflnumber))

    # --- execution/special/nnphases/phase[@mkfluid='0'] ---
    phase = root.find("execution/special/nnphases/phase[@mkfluid='0']")
    if phase is not None:
        if phase_rhop is not None:
            el = phase.find("rhop")
            if el is not None:
                el.set("value", str(phase_rhop))
        if visco_nn is not None:
            el = phase.find("visco")
            if el is not None:
                el.set("value", str(visco_nn))
        if tau_yield is not None:
            el = phase.find("tau_yield")
            if el is not None:
                el.set("value", str(tau_yield))
        if HBP_m is not None:
            el = phase.find("HBP_m")
            if el is not None:
                el.set("value", str(HBP_m))
        if HBP_n is not None:
            el = phase.find("HBP_n")
            if el is not None:
                el.set("value", str(HBP_n))

    # --- execution/parameters/parameter[@key=...] ---
    _set_exec_param(root, "Visco", Visco)
    _set_exec_param(root, "DensityDT", DensityDT)
    _set_exec_param(root, "DensityDTvalue", DensityDTvalue)
    _set_exec_param(root, "TimeMax", TimeMax)
    _set_exec_param(root, "TimeOut", TimeOut)

    # Ensure output directory exists
    Path(output_xml).parent.mkdir(parents=True, exist_ok=True)

    # Write the modified (and now standard-compliant) XML
    tree = ET.ElementTree(root)
    ET.indent(tree, space="    ")
    tree.write(output_xml, encoding="unicode", xml_declaration=True)
    return output_xml


def _set_exec_param(root: ET.Element, key: str, value) -> None:
    """Set execution/parameters/parameter[@key=key] value attribute."""
    if value is None:
        return
    el = root.find(f"execution/parameters/parameter[@key='{key}']")
    if el is not None:
        el.set("value", str(value))
