"""Planning correctness against independent shortest-path and geometry expectations."""

import math
import random
from copy import deepcopy

import networkx as nx
import pytest
from pydantic import ValidationError

from algorithms.path_planning import (
    AStarPlanner, CostWeights, PlanningContext, PlanningError, plan_path,
)
from core.models import (
    AirspaceRestriction, Building, CityConfig, GeoPoint, Position3D,
    PrecipitationType, Weather,
)
from simulation.environment.builder import rectangle_polygon
from simulation.environment.city import CityEnvironment


def graph_from(positions, edges):
    graph = nx.DiGraph()
    for name, xyz in positions.items():
        graph.add_node(name, position=Position3D(x=xyz[0], y=xyz[1], z=xyz[2]))
    for start, end in edges:
        graph.add_edge(start, end, capacity=10, current_flow=0, risk_level=0)
    return graph


def detour_graph():
    return graph_from(
        {"S": (100, 100, 120), "T": (1100, 100, 120), "D": (600, 600, 120)},
        [("S", "T"), ("S", "D"), ("D", "T")],
    )


def distance_weights(**overrides):
    return CostWeights(**({"distance": 1, "risk": 0, "congestion": 0,
                           "energy": 0, "weather": 0} | overrides))


def test_weighted_astar_matches_independent_dijkstra_oracle():
    rng = random.Random(28)
    graph = nx.DiGraph()
    for i in range(24):
        graph.add_node(str(i), position=Position3D(x=rng.uniform(0, 2000),
                                                 y=rng.uniform(0, 2000), z=rng.uniform(50, 180)))
    weights = CostWeights(distance=0.6, risk=2.7, congestion=1.8, energy=0.9, weather=0)
    for i in range(24):
        for j in range(24):
            if i != j and (j == i + 1 or rng.random() < 0.12):
                a, b = graph.nodes[str(i)]["position"], graph.nodes[str(j)]["position"]
                distance = a.distance_to(b)
                risk, flow = rng.random(), rng.randrange(10)
                oracle = distance / 1000 * (0.6 + 2.7 * risk + 1.8 * flow / 10 + 0.9)
                oracle += 0.9 * 4 * max(0, b.z - a.z) / 1000
                graph.add_edge(str(i), str(j), distance=distance, risk_level=risk,
                               capacity=10, current_flow=flow, oracle=oracle)
    for target in ["7", "14", "23"]:
        result = AStarPlanner().plan("0", target, PlanningContext(graph), weights)
        expected = nx.dijkstra_path_length(graph, "0", target, weight="oracle")
        assert result.total_cost == pytest.approx(expected)
        assert result.total_cost == pytest.approx(sum(result.cost_breakdown.values()))
        assert result.estimated_duration_s == pytest.approx(result.distance_m / 15)


def test_risk_weight_changes_path_without_mutating_input():
    graph = detour_graph()
    graph.edges["S", "T"]["risk_level"] = 1
    original = deepcopy(graph)
    assert plan_path("S", "T", PlanningContext(graph), distance_weights()).node_ids == ["S", "T"]
    safer = plan_path("S", "T", PlanningContext(graph), distance_weights(risk=3))
    assert safer.node_ids == ["S", "D", "T"]
    assert safer.cost_breakdown["risk"] == 0
    assert list(graph.nodes(data=True)) == list(original.nodes(data=True))
    assert list(graph.edges(data=True)) == list(original.edges(data=True))


@pytest.mark.parametrize("attribute,value", [("status", "closed"), ("current_flow", 10)])
def test_closed_and_full_routes_are_hard_constraints(attribute, value):
    graph = detour_graph()
    graph.edges["S", "T"][attribute] = value
    result = plan_path("S", "T", PlanningContext(graph), distance_weights())
    assert result.node_ids == ["S", "D", "T"]
    if attribute == "current_flow":
        assert plan_path("S", "T", PlanningContext(graph, respect_capacity=False),
                         distance_weights()).node_ids == ["S", "T"]


def test_dynamic_replanning_and_explicit_blocked_edges():
    graph = detour_graph()
    assert plan_path("S", "T", PlanningContext(graph)).node_ids == ["S", "T"]
    assert plan_path("S", "T", PlanningContext(graph, blocked_edges={("S", "T")})).node_ids == ["S", "D", "T"]
    graph.edges["S", "T"]["status"] = "closed"
    assert plan_path("S", "T", PlanningContext(graph)).node_ids == ["S", "D", "T"]
    graph.edges["S", "T"]["status"] = "open"
    assert plan_path("S", "T", PlanningContext(graph)).node_ids == ["S", "T"]


def test_restriction_is_height_aware_and_can_be_deactivated():
    graph = detour_graph()
    restriction = AirspaceRestriction(polygon=rectangle_polygon(600, 100, 2, 40),
                                     min_altitude=110, max_altitude=130)
    context = PlanningContext(graph, restrictions=[restriction])
    assert plan_path("S", "T", context).node_ids == ["S", "D", "T"]
    restriction.max_altitude = 119
    assert plan_path("S", "T", context).node_ids == ["S", "T"]
    restriction.max_altitude = 130
    restriction.active = False
    assert plan_path("S", "T", context).node_ids == ["S", "T"]


def test_climbing_segment_checks_actual_intersection_altitude():
    graph = graph_from({"S": (0, 0, 0), "T": (100, 0, 100)}, [("S", "T")])
    restriction = AirspaceRestriction(polygon=rectangle_polygon(90, 0, 2, 20),
                                     min_altitude=89, max_altitude=91)
    with pytest.raises(PlanningError) as error:
        plan_path("S", "T", PlanningContext(graph, restrictions=[restriction]))
    assert error.value.reason == "no_path"
    restriction.min_altitude, restriction.max_altitude = 40, 60
    result = plan_path("S", "T", PlanningContext(graph, restrictions=[restriction]))
    assert result.distance_m == pytest.approx(math.sqrt(20000))
    assert result.cost_breakdown["energy"] == pytest.approx((math.sqrt(20000) / 1000 + 0.4) * 0.8)


def test_city_geometry_rejects_narrow_obstacle_and_out_of_bounds_endpoint():
    graph = detour_graph()
    city = CityEnvironment(
        CityConfig(origin=GeoPoint(latitude=30, longitude=104), generate_buildings=False),
        [Building(footprint=rectangle_polygon(600, 100, 2, 30), height=150)],
    )
    context = PlanningContext(graph, city=city)
    assert plan_path("S", "T", context).node_ids == ["S", "D", "T"]
    graph.nodes["T"]["position"].x = 2100
    with pytest.raises(PlanningError) as error:
        plan_path("S", "T", context)
    assert error.value.reason == "unsafe_endpoint"


def test_thunderstorm_is_hard_constraint_even_with_zero_weather_weight():
    graph = detour_graph()
    weather = Weather(affected_area=rectangle_polygon(600, 100, 2, 40),
                      precipitation=PrecipitationType.THUNDERSTORM)
    assert plan_path("S", "T", PlanningContext(graph, weather=[weather]),
                     distance_weights()).node_ids == ["S", "D", "T"]


def test_weather_cost_accounts_for_wind_direction_visibility_and_rain():
    graph = graph_from({"S": (0, 0, 100), "T": (1000, 0, 100)}, [("S", "T"), ("T", "S")])
    weather = Weather(affected_area=rectangle_polygon(500, 0, 1200, 100),
                      wind_speed=15, wind_direction=90, visibility_m=2500,
                      precipitation=PrecipitationType.LIGHT_RAIN)
    context = PlanningContext(graph, weather=[weather])
    weights = distance_weights(weather=1)
    upwind = plan_path("S", "T", context, weights)
    downwind = plan_path("T", "S", context, weights)
    assert upwind.cost_breakdown["weather"] == pytest.approx(1 + 0.5 + 0.25)
    assert downwind.cost_breakdown["weather"] == pytest.approx(0.5 + 0.25)
    context.weather.append(weather.model_copy(deep=True))
    assert plan_path("S", "T", context, weights).total_cost == pytest.approx(upwind.total_cost)


def test_range_fallback_identifies_shortest_distance_heuristic_honestly():
    graph = detour_graph()
    graph.edges["S", "T"]["risk_level"] = 1
    weights = distance_weights(risk=3)
    assert plan_path("S", "T", PlanningContext(graph), weights).node_ids == ["S", "D", "T"]
    result = plan_path("S", "T", PlanningContext(graph, max_distance_m=1100), weights)
    assert result.node_ids == ["S", "T"]
    assert result.algorithm == "dijkstra_range_fallback"
    assert result.distance_m == 1000
    assert result.total_cost == 4
    assert "not a guarantee" in result.explanation
    with pytest.raises(PlanningError) as error:
        plan_path("S", "T", PlanningContext(graph, max_distance_m=999), weights)
    assert error.value.reason == "range_limit"
    assert error.value.details["shortest_distance_m"] == 1000


def test_same_source_target_is_zero_length_only_if_endpoint_is_safe():
    graph = detour_graph()
    result = plan_path("S", "S", PlanningContext(graph, max_distance_m=0))
    assert result.node_ids == ["S"]
    assert result.distance_m == result.total_cost == result.estimated_duration_s == 0
    restriction = AirspaceRestriction(polygon=rectangle_polygon(100, 100, 20, 20))
    with pytest.raises(PlanningError) as error:
        plan_path("S", "S", PlanningContext(graph, restrictions=[restriction]))
    assert error.value.reason == "unsafe_endpoint"


def test_no_path_explains_rejection_and_unknown_waypoint():
    graph = detour_graph()
    for _, _, attrs in graph.edges(data=True):
        attrs["status"] = "closed"
    with pytest.raises(PlanningError) as error:
        plan_path("S", "T", PlanningContext(graph))
    assert error.value.reason == "no_path"
    assert error.value.details["rejected_edges"] == {"closed_route": 3}
    with pytest.raises(PlanningError) as error:
        plan_path("S", "MISSING", PlanningContext(graph))
    assert error.value.reason == "unknown_waypoint"


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf"), -float("inf")])
def test_weights_reject_negative_and_nonfinite_values(value):
    with pytest.raises(ValidationError):
        CostWeights(risk=value)


def test_all_zero_weights_are_allowed_and_disable_heuristic():
    graph = detour_graph()
    weights = CostWeights(**dict.fromkeys(CostWeights.model_fields, 0))
    result = plan_path("S", "T", PlanningContext(graph), weights)
    assert result.total_cost == 0
    assert result.node_ids[0] == "S" and result.node_ids[-1] == "T"


@pytest.mark.parametrize("change", [
    {"speed_mps": 0}, {"speed_mps": float("inf")},
    {"max_distance_m": -1}, {"max_distance_m": float("nan")},
])
def test_invalid_context_parameters_fail_before_search(change):
    with pytest.raises(PlanningError) as error:
        plan_path("S", "T", PlanningContext(detour_graph(), **change))
    assert error.value.reason == "invalid_context"


@pytest.mark.parametrize("attribute,value", [
    ("capacity", 0), ("current_flow", -1), ("risk_level", 2), ("distance", float("inf")),
])
def test_invalid_edge_data_is_not_silently_used(attribute, value):
    graph = detour_graph()
    graph.edges["S", "T"][attribute] = value
    with pytest.raises(PlanningError) as error:
        plan_path("S", "T", PlanningContext(graph))
    assert error.value.reason == "invalid_context"


def test_declared_distance_cannot_undercut_geometric_heuristic():
    graph = detour_graph()
    graph.edges["S", "T"]["distance"] = 1
    result = plan_path("S", "T", PlanningContext(graph), distance_weights())
    assert result.distance_m == 1000
    assert result.total_cost == 1
