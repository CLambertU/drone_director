"""Nonnegative multi-criteria A* with hard geometry, weather and capacity constraints."""

import math
from collections import Counter
from copy import deepcopy

import networkx as nx

from algorithms.path_planning.models import (
    CostWeights, PlanningContext, PlanningError, PlanningResult,
)
from core.models import Position3D, PrecipitationType, RouteStatus

_RAIN_PENALTY = {
    PrecipitationType.NONE: 0.0,
    PrecipitationType.LIGHT_RAIN: 0.25,
    PrecipitationType.RAIN: 0.75,
    PrecipitationType.SNOW: 1.0,
    PrecipitationType.HAIL: 2.0,
}


def _constraint(start, end, context: PlanningContext) -> str | None:
    if context.city is not None and not context.city.is_segment_clear(start, end):
        return "obstacle_or_boundary"
    for restriction in context.restrictions:
        if restriction.active and restriction.polygon.intersects_prism(
            start, end, restriction.min_altitude, restriction.max_altitude
        ):
            return "airspace_restriction"
    for weather in context.weather:
        if weather.precipitation == PrecipitationType.THUNDERSTORM and \
                weather.affected_area.intersects_segment(start.xy, end.xy):
            return "thunderstorm"
    return None


def _weather_penalty(start: Position3D, end: Position3D, context: PlanningContext) -> float:
    """Whole-edge exposure is conservative; overlapping observations use the worst one."""
    horizontal_distance = start.horizontal_distance_to(end)
    east = (end.x - start.x) / horizontal_distance if horizontal_distance else 0.0
    north = (end.y - start.y) / horizontal_distance if horizontal_distance else 0.0
    worst = 0.0
    for weather in context.weather:
        if not weather.affected_area.intersects_segment(start.xy, end.xy):
            continue
        bearing = math.radians(weather.wind_direction)  # meteorological direction FROM
        headwind = max(0.0, weather.wind_speed * (east * math.sin(bearing) + north * math.cos(bearing)))
        crosswind = abs(weather.wind_speed * (east * math.cos(bearing) - north * math.sin(bearing)))
        visibility = max(0.0, (5000.0 - weather.visibility_m) / 5000.0)
        penalty = (headwind + 0.25 * crosswind) / context.speed_mps
        penalty += _RAIN_PENALTY.get(weather.precipitation, 0.0) + visibility
        worst = max(worst, penalty)
    return worst


def _number(value, name: str, *, positive: bool = False) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise PlanningError("invalid_context", f"{name} must be a finite number") from exc
    if not math.isfinite(number) or number < 0 or (positive and number == 0):
        raise PlanningError("invalid_context", f"{name} must be {'positive' if positive else 'nonnegative'} and finite")
    return number


def _weighted_graph(context: PlanningContext, weights: CostWeights):
    graph = nx.DiGraph()
    rejected: Counter = Counter()
    for node, attrs in context.graph.nodes(data=True):
        try:
            position = Position3D.model_validate(attrs["position"])
        except (KeyError, ValueError, TypeError) as exc:
            raise PlanningError("invalid_context", f"Node {node} has no valid position") from exc
        graph.add_node(node, position=position.model_copy(deep=True))

    for source, target, attrs in context.graph.edges(data=True):
        if (source, target) in context.blocked_edges:
            rejected["blocked_edge"] += 1
            continue
        if attrs.get("status", RouteStatus.OPEN) == RouteStatus.CLOSED:
            rejected["closed_route"] += 1
            continue
        capacity = _number(attrs.get("capacity", 10), "capacity", positive=True)
        flow = _number(attrs.get("current_flow", 0), "current_flow")
        utilization = flow / capacity
        if context.respect_capacity and utilization >= 1:
            rejected["capacity"] += 1
            continue
        start, end = graph.nodes[source]["position"], graph.nodes[target]["position"]
        cache = context.segment_cache
        key = (start.x, start.y, start.z, end.x, end.y, end.z, context.speed_mps)
        exposure = cache.get(key) if cache is not None else None
        if exposure is None:
            constraint = _constraint(start, end, context)
            exposure = (constraint, _weather_penalty(start, end, context) if constraint is None else 0.0)
            if cache is not None:
                cache[key] = exposure
        constraint, weather_penalty = exposure
        if constraint is not None:
            rejected[constraint] += 1
            continue
        distance = start.distance_to(end)
        # A declared longer segment may represent measured distance. Never shorten geometry.
        distance = max(distance, _number(attrs.get("distance", distance), "distance"))
        risk = _number(attrs.get("risk_level", 0), "risk_level")
        if risk > 1:
            raise PlanningError("invalid_context", "risk_level must be in [0, 1]")
        distance_km = distance / 1000.0
        climb_km = max(0.0, end.z - start.z) / 1000.0
        terms = {
            "distance": distance_km * weights.distance,
            "risk": distance_km * risk * weights.risk,
            "congestion": distance_km * utilization * weights.congestion,
            "energy": (distance_km + 4.0 * climb_km) * weights.energy,
            "weather": distance_km * weather_penalty * weights.weather,
        }
        total = sum(terms.values())
        if not math.isfinite(total):
            raise PlanningError("invalid_context", "Edge cost overflowed; check coordinates and weights")
        graph.add_edge(source, target, distance_m=distance, cost=total, breakdown=terms)
    return graph, dict(rejected)


def plan_path(source: str, target: str, context: PlanningContext,
              weights: CostWeights | None = None) -> PlanningResult:
    """Plan from one coherent environment snapshot, without mutating it.

    A range-limited fallback minimizes distance on the same feasible graph, not the
    constrained weighted objective. It is explicitly identified in the result.
    """
    weights = CostWeights.model_validate((weights or CostWeights()).model_dump())
    speed_mps = _number(context.speed_mps, "speed_mps", positive=True)
    max_distance_m = (_number(context.max_distance_m, "max_distance_m")
                      if context.max_distance_m is not None else None)
    if not context.graph.is_directed() or context.graph.is_multigraph():
        raise PlanningError("invalid_context", "Planning requires a directed graph without parallel edges")
    if source not in context.graph or target not in context.graph:
        raise PlanningError("unknown_waypoint", "Source or destination does not exist",
                            {"source": source, "target": target})

    # Parent state manager supplies the snapshot under its lock. Copy mutable graph
    # attributes/observations so later cost evaluation cannot change the search.
    snapshot = PlanningContext(
        graph=context.graph if context.owned_snapshot else deepcopy(context.graph), city=context.city,
        restrictions=list(context.restrictions) if context.owned_snapshot else deepcopy(context.restrictions),
        weather=list(context.weather) if context.owned_snapshot else deepcopy(context.weather),
        speed_mps=speed_mps, max_distance_m=max_distance_m,
        respect_capacity=context.respect_capacity, blocked_edges=set(context.blocked_edges),
        segment_cache=context.segment_cache if context.owned_snapshot else None,
    )
    graph, rejected = _weighted_graph(snapshot, weights)
    for endpoint in (source, target):
        position = graph.nodes[endpoint]["position"]
        constraint = _constraint(position, position, snapshot)
        if constraint is not None:
            raise PlanningError("unsafe_endpoint", f"Endpoint {endpoint} is blocked by {constraint}",
                                {"endpoint": endpoint, "constraint": constraint})

    def heuristic(node, destination):
        return weights.distance * graph.nodes[node]["position"].distance_to(
            graph.nodes[destination]["position"]) / 1000.0

    try:
        node_ids = nx.astar_path(graph, source, target, heuristic=heuristic, weight="cost")
    except nx.NetworkXNoPath as exc:
        raise PlanningError("no_path", "No path satisfies the active hard constraints",
                            {"source": source, "target": target, "rejected_edges": rejected}) from exc

    def path_distance(nodes):
        return sum(graph.edges[a, b]["distance_m"] for a, b in zip(nodes, nodes[1:]))

    algorithm = "astar"
    explanation = ("A* minimizes a nonnegative weighted sum of distance, risk exposure, "
                   "congestion exposure, energy proxy and weather exposure; hard constraints are filtered first.")
    distance = path_distance(node_ids)
    if snapshot.max_distance_m is not None and distance > snapshot.max_distance_m + 1e-8:
        node_ids = nx.dijkstra_path(graph, source, target, weight="distance_m")
        distance = path_distance(node_ids)
        if distance > snapshot.max_distance_m + 1e-8:
            raise PlanningError("range_limit", "Every feasible route exceeds remaining flight range",
                                {"shortest_distance_m": distance, "max_distance_m": snapshot.max_distance_m})
        algorithm = "dijkstra_range_fallback"
        explanation = ("The weighted A* route exceeded remaining range. Dijkstra selected the shortest "
                       "distance route on the same hard-feasible graph. This is not a guarantee of "
                       "minimum weighted cost among all range-constrained routes.")
    terms = {name: 0.0 for name in CostWeights.model_fields}
    for a, b in zip(node_ids, node_ids[1:]):
        for name, value in graph.edges[a, b]["breakdown"].items():
            terms[name] += value
    return PlanningResult(
        node_ids=node_ids, positions=[graph.nodes[node]["position"] for node in node_ids],
        distance_m=distance, total_cost=sum(terms.values()), cost_breakdown=terms,
        estimated_duration_s=distance / snapshot.speed_mps,
        algorithm=algorithm, explanation=explanation,
    )


class AStarPlanner:
    """Default implementation of PathPlanner; future trained models use the same contract."""

    def plan(self, source: str, target: str, context: PlanningContext,
             weights: CostWeights | None = None) -> PlanningResult:
        return plan_path(source, target, context, weights)
