"""实际边界、狭窄障碍与三维高度裁剪回归测试。"""

import pytest
from pydantic import ValidationError

from core.models import Polygon2D, Position2D, Position3D
from simulation.environment.builder import rectangle_polygon


@pytest.mark.parametrize("point", [(0, 0), (10, 10), (0, 5), (10, 5), (5, 0), (5, 10)])
def test_polygon_includes_all_boundaries(point):
    assert rectangle_polygon(5, 5, 10, 10).contains(Position2D(x=point[0], y=point[1]))


@pytest.mark.parametrize("points", [
    [(0, 0), (1, 0), (2, 0)],
    [(0, 0), (2, 2), (0, 2), (2, 0)],
    [(0, 0), (2, 0), (2, 2), (2, 0), (0, 2)],
    [(0, 0), (3, 0), (1, 0), (1, 3), (0, 3)],
])
def test_degenerate_or_intersecting_polygon_rejected(points):
    with pytest.raises(ValidationError):
        Polygon2D(points=[Position2D(x=x, y=y) for x, y in points])


def test_closed_ring_and_nonfinite_coordinates():
    ring = Polygon2D(points=[Position2D(x=x, y=y) for x, y in [(0, 0), (2, 0), (0, 2), (0, 0)]])
    assert len(ring.points) == 3
    with pytest.raises(ValidationError):
        Position2D(x=float("inf"), y=0)


def test_prism_checks_altitude_at_intersection_not_endpoints_or_average():
    polygon = rectangle_polygon(1.5, 5, 1, 2)
    start, end = Position3D(x=0, y=5, z=0), Position3D(x=10, y=5, z=100)
    assert polygon.intersects_prism(start, end, 10, 15)
    assert not polygon.intersects_prism(start, end, 21, 30)
    assert polygon.intersects_prism(end, start, 10, 15)


def test_prism_tangency_vertical_segments_and_horizontal_clearance():
    polygon = rectangle_polygon(5, 5, 2, 2)
    assert polygon.intersects_prism(Position3D(x=4, y=0, z=10), Position3D(x=4, y=10, z=10), 0, 10)
    assert polygon.intersects_prism(Position3D(x=5, y=5, z=0), Position3D(x=5, y=5, z=20), 10, 10)
    assert not polygon.intersects_prism(Position3D(x=5, y=5, z=11), Position3D(x=5, y=5, z=20), 0, 10)
    a, b = Position3D(x=3, y=0, z=5), Position3D(x=3, y=10, z=5)
    assert polygon.intersects_prism(a, b, 0, 10, horizontal_clearance=1)
    assert not polygon.intersects_prism(a, b, 0, 10, horizontal_clearance=0.99)


def test_concave_polygon_gap_is_clear():
    polygon = Polygon2D(points=[Position2D(x=x, y=y) for x, y in
                               [(0, 0), (6, 0), (6, 6), (4, 6), (4, 2), (2, 2), (2, 6), (0, 6)]])
    assert not polygon.intersects_segment(Position2D(x=3, y=3), Position2D(x=3, y=6))
    assert polygon.intersects_segment(Position2D(x=-1, y=4), Position2D(x=7, y=4))
