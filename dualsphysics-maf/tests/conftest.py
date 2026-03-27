from pathlib import Path

import pytest


@pytest.fixture
def sample_case_xml() -> str:
    return """<root>
    <casedef>
        <constantsdef>
            <gravity x="0" y="0" z="-9.81" />
            <rhop0 value="1000" />
            <coefh value="1.0" />
            <cflnumber value="0.2" />
        </constantsdef>
    </casedef>
    <execution>
        <special>
            <nnphases>
                <phase mkfluid="0">
                    <rhop value="1000" />
                    <visco value="0.01" />
                    <tau_yield value="0.0" />
                    <HBP_m value="1.0" />
                    <HBP_n value="1.0" />
                </phase>
            </nnphases>
        </special>
        <parameters>
            <parameter key="Visco" value="0.01" />
            <parameter key="DensityDT" value="3" />
            <parameter key="DensityDTvalue" value="0.1" />
            <parameter key="TimeMax" value="1.0" />
            <parameter key="TimeOut" value="0.1" />
        </parameters>
    </execution>
</root>
"""


@pytest.fixture
def write_case_xml(tmp_path: Path, sample_case_xml: str):
    def _write(name: str = "Case_Def.xml", content: str | None = None) -> Path:
        path = tmp_path / name
        path.write_text(content or sample_case_xml, encoding="utf-8")
        return path

    return _write


