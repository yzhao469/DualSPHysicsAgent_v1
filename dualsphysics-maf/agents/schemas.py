"""Pydantic models for the simulation workflow."""

from dataclasses import dataclass

from pydantic import BaseModel


class PhysicsParams(BaseModel):
    """Physics and execution parameters for modify_xml."""

    # constantsdef
    gravity_z: float = -9.81
    rhop0: float
    coefh: float = 0.91924
    cflnumber: float = 0.1
    # non-Newtonian phase (mkfluid=0)
    phase_rhop: float
    visco_nn: float
    tau_yield: float
    HBP_m: float
    HBP_n: float
    # execution/parameters
    Visco: float
    DensityDT: int = 3
    DensityDTvalue: float = 0.1
    TimeMax: float
    TimeOut: float


class SimulationPlan(BaseModel):
    """Structured output from the reasoning agent."""

    geometry_xml: str  # Full <geometry>...</geometry> XML
    params: PhysicsParams
    probe_points: list[list[float]]  # [[x, y, z], ...]
    reasoning: str  # Brief explanation of choices


@dataclass
class ReviewRequest:
    """Data attached to a HITL request_info call."""

    phase: str  # "plan" or "viz"
    summary: str  # Formatted text to show user
