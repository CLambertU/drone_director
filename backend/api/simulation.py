"""Simulation commands; every returned number comes from the engine snapshot."""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from backend.exceptions import AppError

router = APIRouter(prefix="/api/simulation", tags=["simulation"])


def get_engine(request: Request):
    return request.app.state.engine


class DemoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    aircraft_count: int = Field(default=100, ge=2, le=500)
    seed: int = Field(default=42, ge=0)


class SpeedRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    speed: float = Field(gt=0, le=100)


class StepRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    steps: int = Field(default=1, ge=1, le=600)


def command(engine, name: str, **kwargs) -> dict:
    try:
        getattr(engine, name)(**kwargs)
        return engine.snapshot(include_environment=True)
    except KeyError as exc:
        raise AppError(404, "not_found", str(exc)) from exc
    except ValueError as exc:
        raise AppError(422, "invalid_simulation_command", str(exc)) from exc
    except RuntimeError as exc:
        raise AppError(409, "simulation_conflict", str(exc)) from exc


@router.get("/state", summary="完整运行快照与实际指标")
def state(engine=Depends(get_engine)) -> dict:
    return engine.snapshot(include_environment=True)


@router.post("/demo", summary="生成可复现的多机演示场景，保持暂停")
def demo(payload: DemoRequest, engine=Depends(get_engine)) -> dict:
    return command(engine, "prepare_demo", **payload.model_dump())


@router.post("/start", summary="启动或恢复仿真")
def start(engine=Depends(get_engine)) -> dict:
    return command(engine, "start")


@router.post("/pause", summary="暂停并保存检查点")
def pause(engine=Depends(get_engine)) -> dict:
    return command(engine, "pause")


@router.post("/speed", summary="设置真实时间到仿真时间的倍率")
def speed(payload: SpeedRequest, engine=Depends(get_engine)) -> dict:
    return command(engine, "set_speed", speed=payload.speed)


@router.post("/step", summary="暂停状态下推进固定仿真步")
def step(payload: StepRequest, engine=Depends(get_engine)) -> dict:
    with engine.registry.lock:
        if engine.running:
            raise AppError(409, "simulation_running", "请先暂停，再执行单步推进")
        return command(engine, "step", steps=payload.steps)


@router.get("/report", summary="下载实际运行指标及事件处理结果")
def report(engine=Depends(get_engine)) -> dict:
    return engine.report()
