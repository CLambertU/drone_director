"""气象接口。"""

from backend.api._crud import build_crud_router
from core.models import Weather

router = build_crud_router(
    prefix="/api/weather",
    tag="weather",
    model_type=Weather,
    repo_attr="weather",
    resource_name="气象区域",
)
