"""ENU <-> WGS84 坐标转换测试。"""

from __future__ import annotations

import math

from pytest import approx

from core.coords import GeoOrigin
from core.models.geometry import Position3D


def make_origin() -> GeoOrigin:
    return GeoOrigin(latitude_deg=30.5728, longitude_deg=104.0668, altitude=0)


def test_origin_maps_to_zero():
    enu = make_origin().geo_to_enu(30.5728, 104.0668, 0)
    assert enu.x == approx(0.0, abs=1e-6)
    assert enu.y == approx(0.0, abs=1e-6)
    assert enu.z == 0.0


def test_east_and_north_directions():
    origin = make_origin()
    east = origin.geo_to_enu(30.5728, 104.0668 + 0.001, 0)
    north = origin.geo_to_enu(30.5728 + 0.001, 104.0668, 0)
    # 经度增大 -> x(东) 为正，纬度增大 -> y(北) 为正
    assert east.x > 90 and abs(east.y) < 0.01
    assert north.y > 105 and abs(north.x) < 0.01


def test_roundtrip_consistency():
    origin = make_origin()
    pos = Position3D(x=1234.5, y=678.9, z=120.0)
    lat, lon, alt = origin.enu_to_geo(pos)
    back = origin.geo_to_enu(lat, lon, alt)
    assert back.distance_to(pos) < 1e-6


def test_altitude_preserved():
    origin = make_origin()
    enu = origin.geo_to_enu(30.5728, 104.0668, 150.0)
    assert math.isclose(enu.z, 150.0)


def test_known_equatorial_ecef_and_negative_up():
    origin = GeoOrigin(0, 0, 100)
    assert origin.geo_to_enu(0, 0, 50).z == approx(-50.0, abs=1e-8)
    longitude = 0.1
    point = origin.geo_to_enu(0, longitude, 0)
    assert point.x == approx(6378137.0 * math.sin(math.radians(longitude)), abs=1e-7)
    assert point.y == approx(0.0, abs=1e-7)
    assert point.z == approx(6378137.0 * (math.cos(math.radians(longitude)) - 1) - 100, abs=1e-7)


def test_roundtrip_city_extent_poles_and_antimeridian():
    for lat, lon in ((30.5, 104), (90, 180), (-90, -180), (0, 179.999)):
        origin = GeoOrigin(lat, lon, 500)
        for position in (Position3D(x=50000, y=-25000, z=-100), Position3D(x=-15000, y=18000, z=2000)):
            geographic = origin.enu_to_geo(position)
            assert -90 <= geographic[0] <= 90 and -180 <= geographic[1] <= 180
            assert origin.geo_to_enu(*geographic).distance_to(position) < 0.001


def test_antimeridian_is_local_distance():
    point = GeoOrigin(0, 179.999, 0).geo_to_enu(0, -179.999, 0)
    assert point.x == approx(222.639, abs=0.001)
    assert abs(point.y) < 1e-8
