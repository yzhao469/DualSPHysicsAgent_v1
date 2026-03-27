import pytest
from pydantic import ValidationError

from agents.schemas import PhysicsParams, SimulationPlan

pytestmark = pytest.mark.unit


def test_physics_params_applies_defaults():
    params = PhysicsParams(
        rhop0=1500,
        phase_rhop=1500,
        visco_nn=0.2,
        tau_yield=0.01,
        HBP_m=10,
        HBP_n=1.2,
        Visco=0.2,
        TimeMax=2.0,
        TimeOut=0.1,
    )

    assert params.gravity_z == -9.81
    assert params.coefh == 1.0
    assert params.cflnumber == 0.2
    assert params.DensityDT == 3
    assert params.DensityDTvalue == 0.1


def test_simulation_plan_validates_nested_params():
    plan = SimulationPlan.model_validate(
        {
            "geometry_xml": "<geometry />",
            "params": {
                "rhop0": 1500,
                "phase_rhop": 1500,
                "visco_nn": 0.2,
                "tau_yield": 0.01,
                "HBP_m": 10,
                "HBP_n": 1.2,
                "Visco": 0.2,
                "TimeMax": 2.0,
                "TimeOut": 0.1,
            },
            "reasoning": "Derived from the scenario constraints.",
        }
    )

    assert isinstance(plan.params, PhysicsParams)


def test_physics_params_requires_mandatory_fields():
    with pytest.raises(ValidationError):
        PhysicsParams()
