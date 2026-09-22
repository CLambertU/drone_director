"""Planning inputs and replaceable planner contract; independent of API and storage."""

from dataclasses import dataclass, field
from typing import Protocol

import networkx as nx
from pydantic import BaseModel, ConfigDict, Field

from core.models import AirspaceRestriction, Position3D, Weather


class CostWeights(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    distance: float = Field(default=1.0, ge=0)
    risk: float = Field(default=2.0, ge=0)
    congestion: float = Field(default=1.5, ge=0)
    energy: float = Field(default=0.8, ge=0)
    weather: float = Field(default=3.0, ge=0)


class CollisionEnvironment(Protocol):
    def is_segment_clear(self, start: Position3D, end: Position3D) -> bool: ...


@dataclass
class PlanningContext:
    """Caller supplies a coherent snapshot; planning does not reserve route capacity."""

    graph: nx.DiGraph
    city: CollisionEnvironment | None = None
    restrictions: list[AirspaceRestriction] = field(default_factory=list)
    weather: list[Weather] = field(default_factory=list)
    speed_mps: float = 15.0
    max_distance_m: float | None = None
    respect_capacity: bool = True
    blocked_edges: set[tuple[str, str]] = field(default_factory=set)


class PlanningResult(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    node_ids: list[str]
    positions: list[Position3D]
    distance_m: float = Field(ge=0)
    total_cost: float = Field(ge=0)
    cost_breakdown: dict[str, float]
    estimated_duration_s: float = Field(ge=0)
    algorithm: str = "astar"
    explanation: str


class PlanningError(ValueError):
    """Structured failure: no path is ever fabricated through a hard constraint."""

    def __init__(self, reason: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.reason = reason
        self.details = details or {}


class PathPlanner(Protocol):
    def plan(self, source: str, target: str, context: PlanningContext,
             weights: CostWeights | None = None) -> PlanningResult: ...
