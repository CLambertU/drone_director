"""任务接口。"""

from backend.api._crud import build_crud_router
from core.models import Mission

router = build_crud_router(
    prefix="/api/missions",
    tag="missions",
    model_type=Mission,
    repo_attr="missions",
    resource_name="任务",
)
