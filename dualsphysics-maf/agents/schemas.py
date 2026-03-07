"""Pydantic models for the simulation workflow."""

from dataclasses import dataclass
from typing import Literal

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

    geometry_xml: str | None = None  # Full <geometry>...</geometry> XML
    params: PhysicsParams
    probe_points: list[list[float]]  # [[x, y, z], ...]
    reasoning: str  # Brief explanation of choices


@dataclass
class ReviewRequest:
    """Data attached to a HITL request_info call."""

    phase: str  # "plan" or "viz"
    summary: str  # Formatted text to show user


@dataclass
class ReviewResult:
    """Output of ReviewExecutor after classifying user feedback."""

    route: Literal["build", "sim", "analyze", "full_replan", "done"]
    feedback: str
    phase: str  # "plan", "viz", or "results"


@dataclass
class PatchRequest:
    """Request to LLM-patch the current case XML."""

    feedback: str
    phase: str  # "plan" or "viz"


@dataclass
class ManualEditRequest:
    """Request for user to manually edit the case XML."""

    phase: str  # "plan" or "viz"


@dataclass
class ManualEditAck:
    """Data attached to request_info when waiting for manual edit completion."""

    file_path: str
    message: str


@dataclass
class AnalysisRequest:
    """User-requested post-processing analysis."""

    feedback: str


@dataclass
class AnalysisResult:
    """Output of AnalyzeExecutor."""

    run_dir: str
    success: bool
    message: str  # Summary of what was produced
    output_files: list[str]


@dataclass
class BuildResult:
    """Output of BuildExecutor after the build pipeline."""

    run_dir: str
    success: bool
    message: str
