"""Pydantic models for the simulation workflow."""

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel


class PhysicsParams(BaseModel):
    """Physics and execution parameters for modify_xml."""

    # constantsdef
    gravity_z: float = -9.81
    rhop0: float
    coefh: float = 1.0
    cflnumber: float = 0.2
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

    geometry_xml: str | None = None  # Full <geometry>...</geometry> XML
    params: PhysicsParams
    probe_points: list[list[float]]  # [[x, y, z], ...]
    reasoning: str  # Brief explanation of choices


@dataclass
class SetupReviewRequest:
    """Data attached to a HITL request_info call in the setup review loop."""

    summary: str
    confirm_sim: bool = False


@dataclass
class ResultsLoopRequest:
    """Data attached to a HITL request_info call in the results loop."""

    summary: str
    confirm_revise: bool = False


@dataclass
class ReviewResult:
    """Output of review executors for routing decisions."""

    route: Literal["sim", "full_replan"]
    feedback: str
