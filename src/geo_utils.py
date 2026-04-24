#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import math


def haversine(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    R = 6371
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def find_nearby_cabinets(station, cabinets: list, max_distance_km: float) -> list[dict]:
    nearby = []
    for cab in cabinets:
        dist = haversine(station.longitude, station.latitude, cab.longitude, cab.latitude)
        if dist <= max_distance_km:
            nearby.append(cab.to_nearby_dict(dist))
    return sorted(nearby, key=lambda x: x["距离km"])


def find_nearby_cabinets_by_levels(station, cabinets: list, max_distance_km: float, high_levels: set) -> dict:
    all_nearby = find_nearby_cabinets(station, cabinets, max_distance_km)
    high_level = [c for c in all_nearby if c["等级"] in high_levels]
    return {
        "total": len(all_nearby),
        "high": len(high_level),
        "list": all_nearby[:5],
        "high_list": high_level[:3],
    }
