"""Feasible candidate inputs and explainable rule-resolution outputs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

from algorithms.conflict_detection import Conflict, ConflictThresholds, TrajectoryPoint
from algorithms.conflict_detection.models import validate_trajectory

ResolutionAction = Literal["speed", "altitude", "reroute", "delay"]


class ResolutionWeights(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, validate_assignment=True)

    delay: float = Field(default=1.0, ge=0)
    energy: float = Field(default=1.0, ge=0)
    congestion: float = Field(default=1.0, ge=0)


class ResolutionCandidate(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    action: ResolutionAction
    aircraft_id: str
    trajectory: list[TrajectoryPoint]
    delay_s: float = Field(default=0.0, ge=0)
    extra_energy: float = Field(default=0.0, ge=0)
    congestion_cost: float = Field(default=0.0, ge=0)
    parameters: dict[str, Any] = Field(default_factory=dict)
    feasible: bool = True

    @field_validator("trajectory")
    @classmethod
    def _validate_trajectory(cls, value: list[TrajectoryPoint]) -> list[TrajectoryPoint]:
        validate_trajectory(value)
        return value


@dataclass
class ResolutionEnvironment:
    trajectories: dict[str, list[TrajectoryPoint]]
    candidates: list[ResolutionCandidate]
    priorities: dict[str, int] = field(default_factory=dict)
    thresholds: ConflictThresholds = field(default_factory=ConflictThresholds)
    now: float = 0.0
    weights: ResolutionWeights = field(default_factory=ResolutionWeights)


class Resolution(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    action: Literal["speed", "altitude", "reroute", "delay", "unresolved"]
    aircraft_id: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    cost: float | None = None
    reason: str
    success: bool


class ConflictResolver(Protocol):
    def __call__(self, conflict: Conflict, environment: ResolutionEnvironment) -> Resolution: ...
