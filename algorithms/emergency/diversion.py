"""Reachable, capacity-aware emergency landing selection with a reserved bay."""

from algorithms.path_planning import PlanningError
from core.models import AircraftStatus, MissionStatus, WaypointType
from simulation.engine.planning import plan_flight


def divert_aircraft(engine, aircraft_id: str, range_derating: float = 0.55) -> dict:
    aircraft = engine.aircraft[aircraft_id]
    aircraft.status = AircraftStatus.FAULT
    aircraft.speed = 0.0
    available_range = aircraft.battery * aircraft.max_range_m * range_derating
    options = []
    for bay in sorted(engine.waypoints.values(), key=lambda w: (w.position.distance_to(aircraft.position), w.id)):
        if bay.type != WaypointType.EMERGENCY_BAY or bay.position.z > 1:
            continue
        reserved = sum(value == bay.id for key, value in engine.bay_reservations.items() if key != aircraft_id)
        if reserved >= bay.capacity or aircraft.position.distance_to(bay.position) > available_range:
            continue
        try:
            plan = plan_flight(engine, aircraft, bay.position, max_distance=available_range, emergency_bay=bay.id)
            distance = plan.remaining_distance(aircraft.position)
            options.append((distance, bay.id, plan, bay.position))
        except PlanningError:
            continue
    mission = engine._mission_for(aircraft_id)
    if not options:
        engine.plans.pop(aircraft_id, None)
        aircraft.status = AircraftStatus.EMERGENCY
        if mission:
            mission.status = MissionStatus.FAILED
        engine.alert(aircraft_id, "故障：剩余航程内无安全可达且可用的备降点，需要人工处置")
        return {"success": False, "aircraft_id": aircraft_id, "remaining_range_m": available_range,
                "reason": "no_reachable_available_emergency_bay"}
    distance, bay_id, plan, destination = min(options, key=lambda option: (option[0], option[1]))
    engine.plans[aircraft_id] = plan
    engine.bay_reservations[aircraft_id] = bay_id
    aircraft.destination = destination
    aircraft.priority = 10
    aircraft.status = AircraftStatus.DIVERTING
    # Damage lowers effective full-battery range as well as the decision budget.
    aircraft.max_range_m *= range_derating
    if mission:
        mission.status = MissionStatus.DIVERTED
    engine._measure_occupancy()
    return {"success": True, "aircraft_id": aircraft_id, "remaining_range_m": available_range,
            "bay_id": bay_id, "planned_distance_m": distance,
            "path": [position.model_dump() for position in plan.positions], "landed": False}
