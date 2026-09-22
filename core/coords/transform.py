"""WGS84 大地坐标与局部 ENU 转换，经 ECEF 地心坐标实现。

ENU 的 z 是相对原点切平面的天向坐标，不是离地高或椭球高差。
转换保留负 z，不进行飞行合法性裁剪；所有角度输入输出均为度。
"""

from __future__ import annotations

import math

from core.models.geometry import Position3D

_WGS84_A = 6378137.0
_WGS84_E2 = 6.69437999014e-3
_WGS84_B = _WGS84_A * math.sqrt(1 - _WGS84_E2)


def _ecef(latitude: float, longitude: float, altitude: float) -> tuple[float, float, float]:
    if not all(math.isfinite(value) for value in (latitude, longitude, altitude)):
        raise ValueError("大地坐标必须是有限数")
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError("纬度/经度超出 WGS84 范围")
    lat, lon = math.radians(latitude), math.radians(longitude)
    sin_lat, cos_lat = math.sin(lat), math.cos(lat)
    n = _WGS84_A / math.sqrt(1 - _WGS84_E2 * sin_lat * sin_lat)
    return ((n + altitude) * cos_lat * math.cos(lon),
            (n + altitude) * cos_lat * math.sin(lon),
            (n * (1 - _WGS84_E2) + altitude) * sin_lat)


class GeoOrigin:
    """局部 ENU 原点，支持极点和跨 ±180° 经线。"""

    def __init__(self, latitude_deg: float, longitude_deg: float, altitude: float = 0.0):
        self._origin = _ecef(latitude_deg, longitude_deg, altitude)
        self.lat0, self.lon0 = math.radians(latitude_deg), math.radians(longitude_deg)
        self.alt0 = altitude
        self._slat, self._clat = math.sin(self.lat0), math.cos(self.lat0)
        self._slon, self._clon = math.sin(self.lon0), math.cos(self.lon0)

    def geo_to_enu(self, latitude_deg: float, longitude_deg: float, altitude: float = 0.0) -> Position3D:
        x, y, z = (a - b for a, b in zip(_ecef(latitude_deg, longitude_deg, altitude), self._origin))
        return Position3D(
            x=-self._slon * x + self._clon * y,
            y=-self._slat * self._clon * x - self._slat * self._slon * y + self._clat * z,
            z=self._clat * self._clon * x + self._clat * self._slon * y + self._slat * z,
        )

    def enu_to_geo(self, position: Position3D) -> tuple[float, float, float]:
        """返回 (纬度, 经度, 椭球高米)，城市尺度往返误差小于毫米。"""
        east, north, up = position.x, position.y, position.z
        x = self._origin[0] - self._slon * east - self._slat * self._clon * north + self._clat * self._clon * up
        y = self._origin[1] + self._clon * east - self._slat * self._slon * north + self._clat * self._slon * up
        z = self._origin[2] + self._clat * north + self._slat * up
        p = math.hypot(x, y)
        if p < 1e-9:
            if abs(z) < 1e-9:
                raise ValueError("地心位置没有唯一大地坐标")
            return math.copysign(90.0, z), math.degrees(self.lon0), abs(z) - _WGS84_B
        lat = math.atan2(z, p * (1 - _WGS84_E2))
        for _ in range(12):
            n = _WGS84_A / math.sqrt(1 - _WGS84_E2 * math.sin(lat) ** 2)
            updated = math.atan2(z + _WGS84_E2 * n * math.sin(lat), p)
            if abs(updated - lat) < 1e-14:
                lat = updated
                break
            lat = updated
        n = _WGS84_A / math.sqrt(1 - _WGS84_E2 * math.sin(lat) ** 2)
        alt = (p / math.cos(lat) - n if abs(math.cos(lat)) > 0.5
               else z / math.sin(lat) - n * (1 - _WGS84_E2))
        return math.degrees(lat), math.degrees(math.atan2(y, x)), alt

