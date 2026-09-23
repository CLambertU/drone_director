"""Metrics are computed from observed movement and task timestamps."""

from core.models import AircraftStatus, MissionStatus, Severity


def collect_metrics(engine) -> dict:
    aircraft = list(engine.aircraft.values())
    missions = list(engine.missions.values())
    routes = list(engine.routes.values())
    distance = sum(engine.distances.values())
    active = [m for m in missions if m.status in (MissionStatus.PENDING, MissionStatus.ASSIGNED,
                                                MissionStatus.IN_PROGRESS)]
    delays = []
    for mission in missions:
        if mission.baseline_duration_s is None:
            delays.append(mission.delay_s)
            continue
        end = mission.completed_sim_time if mission.completed_sim_time is not None else engine.time_s
        if mission.status == MissionStatus.IN_PROGRESS and mission.aircraft_id in engine.plans:
            aircraft_item = engine.aircraft[mission.aircraft_id]
            plan = engine.plans[mission.aircraft_id]
            end += plan.remaining_time(aircraft_item.position)
        delays.append(max(mission.delay_s, end - mission.created_sim_time - mission.baseline_duration_s, 0))
    capacities = sum(r.capacity for r in routes)
    return {
        "aircraft_count": len(aircraft),
        "active_aircraft_count": sum(a.status in (AircraftStatus.EN_ROUTE, AircraftStatus.DIVERTING,
                                                 AircraftStatus.HOVERING, AircraftStatus.EMERGENCY) for a in aircraft),
        "active_mission_count": len(active), "route_count": len(routes),
        "conflict_count": len(engine.conflicts),
        "predicted_conflict_count": engine.detected_conflicts,
        "congested_route_count": sum(engine.occupancy.get(r.id, 0) >= r.capacity for r in routes),
        "alert_count": engine.alert_count,
        "average_delay_s": sum(delays) / len(delays) if delays else 0.0,
        "average_flight_distance_m": distance / len(aircraft) if aircraft else 0.0,
        "total_flight_distance_m": distance,
        "route_utilization": sum(engine.occupancy.values()) / capacities if capacities else 0.0,
        "emergency_response_ms": engine.emergency_response_total_ms / engine.emergency_response_count if engine.emergency_response_count else 0.0,
        "completed_missions": sum(m.status == MissionStatus.COMPLETED for m in missions),
        "resolved_conflicts": engine.resolved_conflicts,
    }
