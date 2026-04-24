#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from dataclasses import dataclass, field


@dataclass
class Station:
    name: str
    city: str
    district: str
    address: str
    terminal_count: str
    attribute: str
    selection_status: str
    longitude: float
    latitude: float

    def to_dict(self) -> dict:
        return {
            "名称": self.name,
            "城市": self.city,
            "地区": self.district,
            "地址": self.address,
            "终端数": self.terminal_count,
            "属性": self.attribute,
            "是否选择": self.selection_status,
            "经度": self.longitude,
            "纬度": self.latitude,
        }


@dataclass
class Cabinet:
    brand: str
    site_name: str
    cabinet_id: str
    slot_count: str
    longitude: float
    latitude: float
    daily_swaps: str
    level: str
    electricity_price: str = ""
    electricity_usage: str = ""

    def to_dict(self) -> dict:
        return {
            "品牌": self.brand,
            "站点": self.site_name,
            "ID": self.cabinet_id,
            "仓数": self.slot_count,
            "经度": self.longitude,
            "纬度": self.latitude,
            "日均换电": self.daily_swaps,
            "等级": self.level,
            "电费单价": self.electricity_price,
            "用电度数": self.electricity_usage,
        }

    def to_nearby_dict(self, distance_km: float) -> dict:
        result = self.to_dict()
        result["距离km"] = round(distance_km, 3)
        return result


@dataclass
class NewSite:
    name: str
    address: str
    longitude: float
    latitude: float

    def to_dict(self) -> dict:
        return {
            "名称": self.name,
            "地址": self.address,
            "经度": self.longitude,
            "纬度": self.latitude,
        }
