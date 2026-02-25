"""XML modifier for DualSPHysics case files.

The base XML uses a few non-standard features (triple-dash comments, unescaped
< and > inside attribute values) that standard parsers reject.  We fix them
in memory before parsing, then write clean XML back.  GenCase reads the
output XML and is lenient, so the cleaned version works fine.
"""
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional


def _preprocess_xml(content: str) -> str:
    """Fix non-standard XML features used in DualSPHysics case files.

    Handles:
    - Triple-dash XML comments: <!---...--->  →  <!-- ... -->
    - Unescaped < and > inside quoted attribute values
    """
    # Fix triple-dash comments
    content = re.sub(
        r'<!---+(.*?)-+-->',
        lambda m: '<!-- ' + re.sub(r'-{2,}', '-', m.group(1).strip()) + ' -->',
        content,
        flags=re.DOTALL,
    )

    # Fix unescaped < and > inside quoted attribute values
    def _fix_attr(m: re.Match) -> str:
        quote = m.group(1)
        val = m.group(2)
        val = re.sub(r'<', '&lt;', val)
        val = re.sub(r'>', '&gt;', val)
        return f'={quote}{val}{quote}'

    content = re.sub(r'=([\"\'])(.*?)\1', _fix_attr, content, flags=re.DOTALL)
    return content


def modify_xml(
    base_xml: str,
    output_xml: str,
    # Standard SPH params
    dp: Optional[float] = None,
    coefh: Optional[float] = None,
    cflnumber: Optional[float] = None,
    Visco: Optional[float] = None,
    DensityDT: Optional[int] = None,
    DensityDTvalue: Optional[float] = None,
    # Simulation time control
    TimeMax: Optional[float] = None,
    TimeOut: Optional[float] = None,
    # Non-Newtonian phase params
    visco_nn: Optional[float] = None,
    tau_yield: Optional[float] = None,
    HBP_m: Optional[float] = None,
    HBP_n: Optional[float] = None,
) -> str:
    """Copy base_xml to output_xml and apply only the provided params.

    Returns the path to the output XML file.
    """
    # Read and preprocess the source XML
    with open(base_xml, "r", encoding="utf-8", errors="replace") as fh:
        raw = fh.read()

    fixed = _preprocess_xml(raw)
    root = ET.fromstring(fixed)

    # --- casedef/geometry/definition[@dp] ---
    if dp is not None:
        el = root.find("casedef/geometry/definition")
        if el is not None:
            el.set("dp", str(dp))

    # --- casedef/constantsdef/* ---
    if coefh is not None:
        el = root.find("casedef/constantsdef/coefh")
        if el is not None:
            el.set("value", str(coefh))

    if cflnumber is not None:
        el = root.find("casedef/constantsdef/cflnumber")
        if el is not None:
            el.set("value", str(cflnumber))

    # --- execution/parameters/parameter[@key=...] ---
    _set_exec_param(root, "Visco", Visco)
    _set_exec_param(root, "DensityDT", DensityDT)
    _set_exec_param(root, "DensityDTvalue", DensityDTvalue)
    _set_exec_param(root, "TimeMax", TimeMax)
    _set_exec_param(root, "TimeOut", TimeOut)

    # --- execution/special/nnphases/phase[@mkfluid='0'] ---
    phase = root.find("execution/special/nnphases/phase[@mkfluid='0']")
    if phase is not None:
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
