import xml.etree.ElementTree as ET

import pytest

from mcp_server.tools.xml_modifier import modify_xml

pytestmark = pytest.mark.unit


def test_modify_xml_updates_requested_parameters_and_creates_parent_dirs(write_case_xml, tmp_path):
    source = write_case_xml()
    output = tmp_path / "nested" / "out" / "Case_Def.xml"

    result = modify_xml(
        str(source),
        str(output),
        gravity_z=-1.5,
        rhop0=1400,
        coefh=0.85,
        cflnumber=0.2,
        phase_rhop=1350,
        visco_nn=0.3,
        tau_yield=0.05,
        HBP_m=5.0,
        HBP_n=1.4,
        Visco=0.4,
        DensityDT=2,
        DensityDTvalue=0.25,
        TimeMax=6.0,
        TimeOut=0.5,
    )

    assert result == str(output)
    assert output.is_file()

    root = ET.parse(output).getroot()
    assert root.find("casedef/constantsdef/gravity").get("z") == "-1.5"
    assert root.find("casedef/constantsdef/rhop0").get("value") == "1400"
    assert root.find("execution/special/nnphases/phase/rhop").get("value") == "1350"
    assert root.find("execution/parameters/parameter[@key='TimeOut']").get("value") == "0.5"


def test_modify_xml_leaves_unspecified_values_unchanged(write_case_xml, tmp_path):
    source = write_case_xml()
    output = tmp_path / "Case_Def.xml"

    modify_xml(str(source), str(output), TimeMax=3.0)

    root = ET.parse(output).getroot()
    assert root.find("execution/parameters/parameter[@key='TimeMax']").get("value") == "3.0"
    assert root.find("execution/parameters/parameter[@key='Visco']").get("value") == "0.01"
    assert root.find("casedef/constantsdef/gravity").get("z") == "-9.81"
