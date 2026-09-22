"""飞行器接口。"""

from backend.api._crud import build_crud_router
from core.models import Aircraft

router = build_crud_router(
    prefix="/api/aircraft",
    tag="aircraft",
    model_type=Aircraft,
    repo_attr="aircraft",
    resource_name="飞行器",
)
