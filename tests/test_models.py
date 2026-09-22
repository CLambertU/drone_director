"""领域模型校验测试。"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from core.models import (
    Aircraft,
    AircraftStatus,
    AirRoute,
    AirspaceRestriction,
    Event,
    EventType,
    Mission,
    Polygon2D,
    Position2D,
    Position3D,
    Severity,
)


def test_aircraft_defaults_and_altitude_view():
    ac = Aircraft(position=Position3D(x=10, y=20, z=120))
    assert ac.status == AircraftStatus.GROUNDED
    assert ac.altitude == 120
    assert ac.id.startswith("AC")


def test_aircraft_battery_range_validation():
    with pytest.raises(ValidationError):
        Aircraft(position=Position3D(), battery=1.5)
    with pytest.raises(ValidationError):
        Aircraft(position=Position3D(), battery=-0.1)


def test_aircraft_heading_and_priority_validation():
    with pytest.raises(ValidationError):
        Aircraft(position=Position3D(), heading=360)
    with pytest.raises(ValidationError):
        Aircraft(position=Position3D(), priority=11)


def test_enu_coordinates_preserve_negative_up_but_reject_nonfinite():
    assert Position3D(x=0, y=0, z=-1).z == -1
    with pytest.raises(ValidationError):
        Position3D(x=0, y=0, z=float("nan"))


def test_position_3d_distance():
    a = Position3D(x=0, y=0, z=0)
    b = Position3D(x=3, y=4, z=0)
    assert a.distance_to(b) == pytest.approx(5.0)


def test_polygon_requires_three_points():
    with pytest.raises(ValidationError):
        Polygon2D(points=[Position2D(x=0, y=0), Position2D(x=1, y=0)])


def test_polygon_contains():
    square = Polygon2D(
        points=[
            Position2D(x=0, y=0),
            Position2D(x=10, y=0),
            Position2D(x=10, y=10),
            Position2D(x=0, y=10),
        ]
    )
    assert square.contains(Position2D(x=5, y=5)) is True
    assert square.contains(Position2D(x=15, y=5)) is False


def test_restriction_altitude_band_validation():
    poly = Polygon2D(
        points=[
            Position2D(x=0, y=0),
            Position2D(x=10, y=0),
            Position2D(x=10, y=10),
        ]
    )
    with pytest.raises(ValidationError):
        AirspaceRestriction(polygon=poly, min_altitude=200, max_altitude=100)


def test_route_utilization_computed():
    route = AirRoute(
        start="WP01", end="WP02", distance=500, capacity=10, current_flow=8
    )
    assert route.utilization == pytest.approx(0.8)


def test_route_capacity_must_be_positive():
    with pytest.raises(ValidationError):
        AirRoute(start="a", end="b", capacity=0)


def test_mission_defaults():
    m = Mission(
        aircraft_id="AC01",
        origin=Position3D(),
        destination=Position3D(x=1, y=1, z=1),
    )
    assert m.id.startswith("MS")
    assert m.created_at is not None


def test_event_defaults():
    e = Event(type=EventType.AIRCRAFT_FAILURE, severity=Severity.EMERGENCY)
    assert e.handled is False
    assert e.timestamp is not None
