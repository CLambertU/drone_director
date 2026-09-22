"""API 路由汇总。"""

from fastapi import APIRouter

from backend.api import (
    aircraft,
    environment,
    events,
    health,
    missions,
    restrictions,
    routes,
    system,
    waypoints,
    weather,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(system.router)
api_router.include_router(environment.router)
api_router.include_router(aircraft.router)
api_router.include_router(waypoints.router)
api_router.include_router(routes.router)
api_router.include_router(missions.router)
api_router.include_router(weather.router)
api_router.include_router(restrictions.router)
api_router.include_router(events.router)
