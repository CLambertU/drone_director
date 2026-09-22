"""低空航路接口。"""

from backend.api._crud import build_crud_router
from core.models import AirRoute

router = build_crud_router(
    prefix="/api/routes",
    tag="routes",
    model_type=AirRoute,
    repo_attr="routes",
    resource_name="航路",
)
