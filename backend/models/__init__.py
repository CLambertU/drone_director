"""Public write schemas; generated measurements and processing fields are read-only."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from core.models import Aircraft, AirspaceRestriction, Weather, Waypoint
from core.models.enums import EventType, MissionStatus, RouteStatus, Severity
from core.models.geometry import Position3D


class WriteInput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    id: str | None = Field(default=None, min_length=1)


class AircraftInput(Aircraft):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    id: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_speed(self):
        if self.speed > self.max_speed:
            raise ValueError("speed cannot exceed max_speed")
        return self


class WaypointInput(Waypoint):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    id: str | None = Field(default=None, min_length=1)


class WeatherInput(Weather):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    id: str | None = Field(default=None, min_length=1)


class RestrictionInput(AirspaceRestriction):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    id: str | None = Field(default=None, min_length=1)


class RouteInput(WriteInput):
    name: str | None = None
    start: str = Field(min_length=1)
    end: str = Field(min_length=1)
    waypoint_ids: list[str] = Field(default_factory=list)
    capacity: int = Field(default=10, ge=1)
    risk_level: float = Field(default=0, ge=0, le=1)
    status: RouteStatus = RouteStatus.OPEN


class MissionInput(WriteInput):
    aircraft_id: str = Field(min_length=1)
    origin: Position3D
    destination: Position3D
    priority: int = Field(default=0, ge=0, le=10)
    status: MissionStatus = MissionStatus.PENDING
    route_id: str | None = None


class EventInput(WriteInput):
    type: EventType
    location: Position3D | None = None
    severity: Severity = Severity.INFO
    description: str = ""
    related_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


INPUT_MODELS = {
    "aircraft": AircraftInput,
    "waypoints": WaypointInput,
    "routes": RouteInput,
    "missions": MissionInput,
    "weather": WeatherInput,
    "restrictions": RestrictionInput,
    "events": EventInput,
}

PROTECTED_FIELDS = {
    "routes": {"current_flow"},
    "missions": {"created_at", "assigned_at", "completed_at"},
    "events": {"timestamp", "handled"},
}
