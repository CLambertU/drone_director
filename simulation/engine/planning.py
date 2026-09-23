"""Join the current physical position to the graph before every fresh search."""

from algorithms.path_planning import CostWeights, PlanningContext, PlanningError, plan_path
from core.models import Position3D
from simulation.aircraft.flight import FlightPlan


class CachedCollisionEnvironment:
    """A city is immutable between environment versions, so exact segment checks are reusable."""

    def __init__(self, city):
        self.city = city
        self.cache: dict[tuple, bool] = {}

    def is_segment_clear(self, start, end):
        key = (start.x, start.y, start.z, end.x, end.y, end.z)
        if key not in self.cache:
            if len(self.cache) > 10000:
                self.cache.clear()
            self.cache[key] = self.city.is_segment_clear(start, end)
        return self.cache[key]


def plan_flight(engine, aircraft, destination: Position3D, *, max_distance=None,
                blocked_edges=None, emergency_bay=None) -> FlightPlan:
    graph = engine.environment.network.graph.copy()
    for _, _, edge in graph.edges(data=True):
        # Occupancy is measured from moving aircraft, not seed counters.
        edge["current_flow"] = max((engine.occupancy.get(r, 0) for r in edge.get("route_ids", [])), default=0)
    source = _attach(graph, aircraft.position, "@current", outbound=True)
    target = _attach(graph, destination, "@destination", outbound=False)
    speed = min(15.0, aircraft.max_speed)
    context = PlanningContext(graph=graph, city=engine.collision_city,
                              restrictions=list(engine.restrictions.values()),
                              weather=list(engine.weather.values()), speed_mps=speed,
                              max_distance_m=max_distance, blocked_edges=blocked_edges or set())
    result = plan_path(source, target, context, engine.weights)
    energy_distance = sum(a.distance_to(b)+4*max(0,b.z-a.z)
                          for a,b in zip(result.positions,result.positions[1:]))
    if max_distance is not None and energy_distance > max_distance + 1e-6:
        raise PlanningError("energy_limit", "可行航路的爬升耗能超出剩余能力",
                            {"energy_equivalent_m":energy_distance,"available_m":max_distance})
    routes = []
    for a, b in zip(result.node_ids, result.node_ids[1:]):
        ids = graph.edges[a, b].get("route_ids", [])
        routes.append(ids[0] if ids else None)
    return FlightPlan(positions=result.positions, node_ids=result.node_ids,
                      speed_mps=speed, route_ids=routes, emergency_bay=emergency_bay)


def _attach(graph, position, name, *, outbound):
    nodes = sorted(((position.distance_to(data["position"]), node)
                    for node, data in graph.nodes(data=True) if not str(node).startswith("@")))
    if nodes and nodes[0][0] < 1e-7:
        return nodes[0][1]
    graph.add_node(name, position=position, capacity=1000, risk_level=0.0)
    # Current-position connectors are checked by exactly the same hard constraints
    # as graph edges. Keep them local; never fabricate a direct destination jump.
    for distance, node in nodes[:4]:
        attrs = dict(distance=distance, capacity=1000, current_flow=0,
                     risk_level=0.0, status="open", route_ids=[])
        graph.add_edge(name, node, **attrs) if outbound else graph.add_edge(node, name, **attrs)
    return name
