"""set_geometry tool — replaces the <geometry> block in a DualSPHysics case XML."""
import xml.etree.ElementTree as ET
from pathlib import Path

from ._xml_utils import preprocess_xml


def set_geometry(base_xml: str, output_xml: str, geometry_xml: str) -> str:
    """Replace the <geometry> block in *base_xml* with *geometry_xml* and write to *output_xml*.

    *geometry_xml* can contain just ``<geometry>...</geometry>``, or both
    ``<geometry>`` and ``<floatings>`` wrapped in a ``<casedef>`` root, e.g.::

        <casedef>
          <geometry>...</geometry>
          <floatings>...</floatings>
        </casedef>

    If the input has two top-level siblings (``<geometry>`` + ``<floatings>``),
    they are auto-wrapped in ``<casedef>`` before parsing.

    Returns a descriptive success or error string.
    """
    # --- Read and parse the base XML ---
    try:
        raw = Path(base_xml).read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return f"ERROR: base XML not found: {base_xml}"

    fixed = preprocess_xml(raw)
    try:
        root = ET.fromstring(fixed)
    except ET.ParseError as exc:
        return f"ERROR: cannot parse base XML: {exc}"

    # --- Parse the geometry XML fragment ---
    # Try parsing as-is first; if it fails (e.g. two root elements), wrap in <casedef>
    floatings = None
    try:
        geom = ET.fromstring(geometry_xml)
    except ET.ParseError:
        # Likely two sibling elements — wrap and retry
        try:
            wrapper = ET.fromstring(f"<casedef>{geometry_xml}</casedef>")
        except ET.ParseError as exc:
            return f"ERROR: cannot parse geometry_xml: {exc}"
        geom = wrapper.find("geometry")
        floatings = wrapper.find("floatings")
        if geom is None:
            return "ERROR: geometry_xml must contain a <geometry> element"
    else:
        # Parsed successfully — check if it's a <casedef> wrapper
        if geom.tag == "casedef":
            wrapper = geom
            geom = wrapper.find("geometry")
            floatings = wrapper.find("floatings")
            if geom is None:
                return "ERROR: <casedef> wrapper must contain a <geometry> element"

    if geom.tag != "geometry":
        return f"ERROR: root tag must be <geometry>, got <{geom.tag}>"

    # --- Validate geometry ---
    defn = geom.find("definition")
    if defn is None:
        return "ERROR: <geometry> must contain <definition>"

    dp_str = defn.get("dp")
    if dp_str is None:
        return "ERROR: <definition> must have a dp attribute"
    if dp_str.startswith("#"):
        pass  # variable reference (e.g. "#Dp") — resolved by GenCase at runtime
    else:
        try:
            dp_val = float(dp_str)
        except ValueError:
            return f"ERROR: dp must be numeric, got '{dp_str}'"
        if dp_val <= 0:
            return f"ERROR: dp must be positive, got {dp_val}"

    if defn.find("pointmin") is None:
        return "ERROR: <definition> must contain <pointmin>"
    if defn.find("pointmax") is None:
        return "ERROR: <definition> must contain <pointmax>"

    mainlist = geom.find("commands/mainlist")
    if mainlist is None:
        return "ERROR: <geometry> must contain <commands><mainlist>"
    if len(list(mainlist)) == 0:
        return "ERROR: <mainlist> must contain at least one drawing command"

    # --- Splice geometry into the case tree ---
    casedef = root.find("casedef")
    if casedef is None:
        return "ERROR: base XML has no <casedef>"

    old_geom = casedef.find("geometry")
    if old_geom is not None:
        casedef.remove(old_geom)

    # Insert geometry right after mkconfig (if present), otherwise at end of casedef
    mkconfig = casedef.find("mkconfig")
    if mkconfig is not None:
        idx = list(casedef).index(mkconfig) + 1
        casedef.insert(idx, geom)
    else:
        casedef.append(geom)

    # --- Handle <floatings> if present ---
    old_floatings = casedef.find("floatings")
    if old_floatings is not None:
        casedef.remove(old_floatings)

    if floatings is not None:
        geom_idx = list(casedef).index(geom)
        casedef.insert(geom_idx + 1, floatings)

    # --- Write output ---
    Path(output_xml).parent.mkdir(parents=True, exist_ok=True)
    tree = ET.ElementTree(root)
    ET.indent(tree, space="    ")
    tree.write(output_xml, encoding="unicode", xml_declaration=True)

    # Build a summary
    n_commands = len(list(mainlist))
    floating_count = len(list(floatings)) if floatings is not None else 0
    summary = f"OK: geometry set in {output_xml} — dp={dp_val}, {n_commands} drawing command(s)"
    if floating_count:
        summary += f", {floating_count} floating body(ies)"
    return summary
