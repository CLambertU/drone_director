"""领域枚举定义。"""

from __future__ import annotations

from enum import Enum


class AircraftStatus(str, Enum):
    """飞行器生命周期状态。"""

    GROUNDED = "grounded"            # 地面待命
    TAKING_OFF = "taking_off"        # 起飞爬升中
    EN_ROUTE = "en_route"            # 航路巡航中
    HOVERING = "hovering"            # 悬停等待
    LANDING = "landing"              # 降落中
    LANDED = "landed"                # 已降落（任务完成）
    DIVERTING = "diverting"          # 备降改航中
    EMERGENCY = "emergency"          # 应急状态
    FAULT = "fault"                  # 故障
    OFFLINE = "offline"              # 离线


class WaypointType(str, Enum):
    """航路点类型。"""

    VERTIPORT = "vertiport"            # 起降场（垂直起降点）
    WAYPOINT = "waypoint"              # 普通航路节点
    EMERGENCY_BAY = "emergency_bay"    # 应急备降点


class RouteStatus(str, Enum):
    """航路运行状态。"""

    OPEN = "open"                # 正常开放
    CONGESTED = "congested"      # 拥堵（流量达到/超过容量）
    RESTRICTED = "restricted"    # 受限（天气/管制导致代价升高，仍可飞）
    CLOSED = "closed"            # 关闭（禁止进入）


class MissionStatus(str, Enum):
    """任务状态。"""

    PENDING = "pending"            # 待分配
    ASSIGNED = "assigned"          # 已分配航路与飞行器
    IN_PROGRESS = "in_progress"    # 执行中
    COMPLETED = "completed"        # 已完成
    DIVERTED = "diverted"          # 已改航备降
    FAILED = "failed"              # 失败
    CANCELLED = "cancelled"        # 已取消


class PrecipitationType(str, Enum):
    """降水类型。"""

    NONE = "none"
    LIGHT_RAIN = "light_rain"
    RAIN = "rain"
    THUNDERSTORM = "thunderstorm"
    SNOW = "snow"
    HAIL = "hail"


class EventType(str, Enum):
    """动态事件类型。"""

    WEATHER = "event_weather"                     # 气象事件（如雷暴）
    AIRSPACE_CLOSURE = "event_airspace_closure"   # 临时空域管制
    AIRCRAFT_FAILURE = "event_aircraft_failure"   # 飞行器故障
    ROUTE_CONGESTION = "event_route_congestion"   # 航路拥堵
    CONFLICT = "event_conflict"                   # 冲突告警
    EMERGENCY_LANDING = "event_emergency_landing"  # 应急备降
    INFO = "event_info"                           # 一般信息


class Severity(str, Enum):
    """事件/告警严重等级。"""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"
