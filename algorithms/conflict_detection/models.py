"""Continuous trajectory conflict contracts; coordinates are local ENU metres."""

from __future__ import annotations

import math
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from core.models.geometry import Position3D


class TrajectoryPoint(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    time: float
    position: Position3D


class ConflictThresholds(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, validate_assignment=True)

    horizontal_m: float = Field(default=30.0, gt=0)
    vertical_m: float = Field(default=15.0, gt=0)
    time_window_s: float = Field(default=10.0, gt=0)


class Conflict(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    aircraft_a: str
    aircraft_b: str
    conflict_time: float
    conflict_position: Position3D
    severity: str


class ConflictDetector(Protocol):
    """A traditional or learned detector must preserve this callable contract."""

    def __call__(
        self, trajectories: dict[str, list[TrajectoryPoint]],
        thresholds: ConflictThresholds | None = None, now: float = 0.0,
    ) -> list[Conflict]: ...


def validate_trajectory(trajectory: list[TrajectoryPoint]) -> None:
    """Empty predictions are allowed; a single point has no extrapolated duration."""
    previous = -math.inf
    for point in trajectory:
        if not isinstance(point, TrajectoryPoint):
            raise ValueError("Trajectory entries must be TrajectoryPoint instances")
        if not all(math.isfinite(v) for v in (
            point.time, point.position.x, point.position.y, point.position.z,
        )):
            raise ValueError("Trajectory timestamps and coordinates must be finite")
        if point.time <= previous:
            raise ValueError("Trajectory timestamps must be strictly increasing")
        previous = point.time
