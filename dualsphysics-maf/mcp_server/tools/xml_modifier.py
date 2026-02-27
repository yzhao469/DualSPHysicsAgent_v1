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


def _find_drawbox_after_mk(
    mainlist: ET.Element, tag: str, mk: int
) -> Optional[ET.Element]:
    """Return the <drawbox> immediately following <setmkfluid mk=...> or <setmkbound mk=...>.

    Comment nodes are skipped. Returns None if not found.
    """
    children = list(mainlist)
    for i, child in enumerate(children):
        if isinstance(child.tag, str) and child.tag == tag and child.get("mk") == str(mk):
            for j in range(i + 1, len(children)):
                if isinstance(children[j].tag, str) and children[j].tag == "drawbox":
                    return children[j]
    return None


def modify_xml(
    base_xml: str,
    output_xml: str,
    # ---- constantsdef ----
    gravity_z: Optional[float] = None,
    rhop0: Optional[float] = None,
    coefh: Optional[float] = None,
    cflnumber: Optional[float] = None,
    # ---- geometry ----
    dp: Optional[float] = None,
    fluid_size_x: Optional[float] = None,
    fluid_size_z: Optional[float] = None,
    channel_length: Optional[float] = None,
    channel_height: Optional[float] = None,
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
    """Copy base_xml to output_xml and apply only the provided params.

    Returns the path to the output XML file.
    """
    # Read and preprocess the source XML
    with open(base_xml, "r", encoding="utf-8", errors="replace") as fh:
        raw = fh.read()

    fixed = _preprocess_xml(raw)
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

    # --- casedef/geometry/definition[@dp] ---
    if dp is not None:
        el = root.find("casedef/geometry/definition")
        if el is not None:
            el.set("dp", str(dp))

    # --- casedef/geometry/commands/mainlist (fluid box + walls) ---
    mainlist = root.find("casedef/geometry/commands/mainlist")
    if mainlist is not None:
        # Fluid column dimensions (mkfluid=0)
        if fluid_size_x is not None or fluid_size_z is not None:
            drawbox = _find_drawbox_after_mk(mainlist, "setmkfluid", 0)
            if drawbox is not None:
                size = drawbox.find("size")
                if size is not None:
                    if fluid_size_x is not None:
                        size.set("x", str(fluid_size_x))
                    if fluid_size_z is not None:
                        size.set("z", str(fluid_size_z))

        # Channel floor length (mk=11)
        if channel_length is not None:
            drawbox = _find_drawbox_after_mk(mainlist, "setmkbound", 11)
            if drawbox is not None:
                size = drawbox.find("size")
                if size is not None:
                    size.set("x", str(channel_length))

            # Right wall x-position must track channel_length (mk=13)
            drawbox = _find_drawbox_after_mk(mainlist, "setmkbound", 13)
            if drawbox is not None:
                point = drawbox.find("point")
                if point is not None:
                    point.set("x", str(round(channel_length - 0.04, 6)))

        # Wall height — both left (mk=12) and right (mk=13) walls
        if channel_height is not None:
            for mk in (12, 13):
                drawbox = _find_drawbox_after_mk(mainlist, "setmkbound", mk)
                if drawbox is not None:
                    size = drawbox.find("size")
                    if size is not None:
                        size.set("z", str(channel_height))

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
