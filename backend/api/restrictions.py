"""空域管制接口。"""

from backend.api._crud import build_crud_router
from core.models import AirspaceRestriction

router = build_crud_router(
    prefix="/api/restrictions",
    tag="restrictions",
    model_type=AirspaceRestriction,
    repo_attr="restrictions",
    resource_name="空域管制区",
)
