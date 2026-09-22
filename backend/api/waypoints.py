"""航路点接口。"""

from backend.api._crud import build_crud_router
from core.models import Waypoint

router = build_crud_router(
    prefix="/api/waypoints",
    tag="waypoints",
    model_type=Waypoint,
    repo_attr="waypoints",
    resource_name="航路点",
)
