"""集中配置。

所有可调参数（服务、算法代价权重、冲突阈值、仿真节拍）统一在此声明，
支持通过 .env 文件或环境变量覆盖，环境变量前缀为 TS_。

示例：
    TS_PORT=9000
    TS_COST_WEIGHT_RISK=2.5
    TS_SEED_ON_STARTUP=true
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="TS_",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---------- 服务 ----------
    app_name: str = "天枢智航——城市低空交通智能规划与自主协同系统"
    environment: str = "development"
    host: str = "127.0.0.1"
    port: int = Field(default=8011, ge=1, le=65535)
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    seed_on_startup: bool = False
    database_path: Path = Path(__file__).resolve().parents[2] / "data/tianshu.sqlite3"

    # ---------- A* 多目标代价权重（第三阶段使用） ----------
    # Cost = w1*distance + w2*risk + w3*congestion + w4*energy + w5*weather
    cost_weight_distance: float = Field(default=1.0, ge=0, allow_inf_nan=False)
    cost_weight_risk: float = Field(default=2.0, ge=0, allow_inf_nan=False)
    cost_weight_congestion: float = Field(default=1.5, ge=0, allow_inf_nan=False)
    cost_weight_energy: float = Field(default=0.8, ge=0, allow_inf_nan=False)
    cost_weight_weather: float = Field(default=3.0, ge=0, allow_inf_nan=False)

    # ---------- 冲突检测阈值（第五阶段使用） ----------
    conflict_horizontal_separation_m: float = Field(default=30.0, gt=0, allow_inf_nan=False)
    conflict_vertical_separation_m: float = Field(default=15.0, gt=0, allow_inf_nan=False)
    conflict_time_window_s: float = Field(default=10.0, gt=0, allow_inf_nan=False)

    # ---------- 仿真参数（第四阶段使用） ----------
    simulation_default_speed: float = Field(default=10.0, gt=0, le=100, allow_inf_nan=False)
    """现实 1 秒对应仿真 10 秒。"""
    simulation_tick_seconds: float = Field(default=1.0, gt=0, le=5, allow_inf_nan=False)
    """单个仿真步长（仿真时间，秒）。"""


settings = Settings()
