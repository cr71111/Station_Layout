#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import math
from Station_Layout.src.geo_utils import find_nearby_cabinets, find_nearby_cabinets_by_levels
from Station_Layout.src.models import NewSite
from Station_Layout.config.settings import (
    SELECTED_STATUS,
    UNSELECTED_STATUS,
    PROXIMITY_THRESHOLDS,
    VALUE_SCORE_WEIGHTS,
    HIGH_LEVELS,
)


def calculate_gps_heat(lon: float, lat: float, gps_data: list, radius_km: float = 3.0) -> int:
    """计算指定位置周围radius_km范围内的GPS点数量"""
    count = 0
    for point in gps_data:
        try:
            p_lon = float(point.get("经度", 0))
            p_lat = float(point.get("纬度", 0))
            dist = math.sqrt((lon - p_lon)**2 + (lat - p_lat)**2) * 111  # 粗略转换为km
            if dist <= radius_km:
                count += 1
        except (ValueError, TypeError):
            continue
    return count


def analyze_selected_stations(stations: list, cabinets: list, gps_data: list = None, threshold: float = 3.0) -> list[dict]:
    results = []
    for station in [s for s in stations if s.selection_status == SELECTED_STATUS]:
        nearby = find_nearby_cabinets(station, cabinets, threshold)
        
        # 计算电费和用电量统计
        total_usage = 0
        avg_price = 0
        price_count = 0
        for cab in nearby:
            try:
                usage = float(cab.get("用电度数", 0) or 0)
                total_usage += usage
                price = cab.get("电费单价", "")
                if price:
                    avg_price += float(price)
                    price_count += 1
            except ValueError:
                pass
        
        avg_price = round(avg_price / price_count, 2) if price_count > 0 else 0
        
        # 计算GPS热度
        gps_heat = calculate_gps_heat(station.longitude, station.latitude, gps_data or [], threshold)
        
        # 计算综合分
        cabinet_score = (
            len([c for c in nearby if c.get("等级") in HIGH_LEVELS]) * VALUE_SCORE_WEIGHTS.get("1km_high", 6)
            + len(nearby) * VALUE_SCORE_WEIGHTS.get("1km_total", 3)
            + total_usage * 0.01
            + avg_price * 2
        )
        gps_score = min(gps_heat / 100, 50)  # GPS热度最高50分
        total_score = round(cabinet_score + gps_score, 1)
        
        station_dict = station.to_dict()
        station_dict["综合分"] = total_score
        station_dict["gps热度"] = gps_heat
        
        results.append({
            "场站": station_dict,
            "附近电柜": nearby,
            "电柜数量": len(nearby),
            "总用电度数": round(total_usage, 1),
            "平均电费单价": avg_price,
            "综合分": total_score,
            "gps热度": gps_heat,
        })
    return sorted(results, key=lambda x: x["综合分"], reverse=True)


def analyze_unselected_stations(stations: list, cabinets: list, gps_data: list = None) -> list[dict]:
    results = []
    for station in [s for s in stations if s.selection_status == UNSELECTED_STATUS]:
        entry = {"场站": station.to_dict()}
        any_found = False

        tier_data = {}
        for th in PROXIMITY_THRESHOLDS:
            tier_info = find_nearby_cabinets_by_levels(station, cabinets, th, HIGH_LEVELS)
            key = f"{int(th)}km"
            tier_data[key] = tier_info
            if tier_info["total"] > 0:
                any_found = True

        if not any_found:
            continue

        entry.update(tier_data)

        # 计算3km内电费和用电量
        nearby_3km = find_nearby_cabinets(station, cabinets, 3.0)
        total_usage = 0
        avg_price = 0
        price_count = 0
        for cab in nearby_3km:
            try:
                usage = float(cab.get("用电度数", 0) or 0)
                total_usage += usage
                price = cab.get("电费单价", "")
                if price:
                    avg_price += float(price)
                    price_count += 1
            except ValueError:
                pass
        avg_price = round(avg_price / price_count, 2) if price_count > 0 else 0

        # 计算GPS热度
        gps_heat = calculate_gps_heat(station.longitude, station.latitude, gps_data or [], 3.0)

        # 综合评分：结合3km电柜情况和GPS热度
        cabinet_score = (
            entry["1km"]["high"] * VALUE_SCORE_WEIGHTS["1km_high"]
            + entry["1km"]["total"] * VALUE_SCORE_WEIGHTS["1km_total"]
            + entry["2km"]["high"] * VALUE_SCORE_WEIGHTS["2km_high"]
            + entry["2km"]["total"] * VALUE_SCORE_WEIGHTS["2km_total"]
            + entry["3km"]["high"] * VALUE_SCORE_WEIGHTS["3km_high"]
            + entry["3km"]["total"] * VALUE_SCORE_WEIGHTS.get("3km_total", 1)
            + total_usage * 0.01
            + avg_price * 2
        )
        gps_score = min(gps_heat / 100, 50)
        total_score = round(cabinet_score + gps_score, 1)

        entry["价值分"] = total_score
        entry["综合分"] = total_score
        entry["3km总用电"] = round(total_usage, 1)
        entry["3km平均电费"] = avg_price
        entry["gps热度"] = gps_heat

        station_dict = station.to_dict()
        station_dict["综合分"] = total_score
        station_dict["gps热度"] = gps_heat
        entry["场站"] = station_dict

        if entry["1km"]["total"] > 0:
            entry["最近档"] = "1km"
        elif entry["2km"]["total"] > 0:
            entry["最近档"] = "2km"
        else:
            entry["最近档"] = "3km"

        results.append(entry)

    return sorted(results, key=lambda x: x["综合分"], reverse=True)


def analyze_new_sites(new_sites: list[NewSite], cabinets: list, gps_data: list = None) -> list[dict]:
    results = []
    for site in new_sites:
        entry = {"站点": site.to_dict()}
        any_found = False

        tier_data = {}
        for th in PROXIMITY_THRESHOLDS:
            tier_info = find_nearby_cabinets_by_levels(site, cabinets, th, HIGH_LEVELS)
            key = f"{int(th)}km"
            tier_data[key] = tier_info
            if tier_info["total"] > 0:
                any_found = True

        entry.update(tier_data)

        # 计算3km内电费和用电量
        nearby_3km = find_nearby_cabinets(site, cabinets, 3.0)
        total_usage = 0
        avg_price = 0
        price_count = 0
        for cab in nearby_3km:
            try:
                usage = float(cab.get("用电度数", 0) or 0)
                total_usage += usage
                price = cab.get("电费单价", "")
                if price:
                    avg_price += float(price)
                    price_count += 1
            except ValueError:
                pass
        avg_price = round(avg_price / price_count, 2) if price_count > 0 else 0

        # 计算GPS热度
        gps_heat = calculate_gps_heat(site.longitude, site.latitude, gps_data or [], 3.0)

        if any_found:
            cabinet_score = (
                entry["1km"]["high"] * VALUE_SCORE_WEIGHTS["1km_high"]
                + entry["1km"]["total"] * VALUE_SCORE_WEIGHTS["1km_total"]
                + entry["2km"]["high"] * VALUE_SCORE_WEIGHTS["2km_high"]
                + entry["2km"]["total"] * VALUE_SCORE_WEIGHTS["2km_total"]
                + entry["3km"]["high"] * VALUE_SCORE_WEIGHTS["3km_high"]
                + entry["3km"]["total"] * VALUE_SCORE_WEIGHTS.get("3km_total", 1)
                + total_usage * 0.01
                + avg_price * 2
            )
        else:
            cabinet_score = 0

        gps_score = min(gps_heat / 100, 50)
        total_score = round(cabinet_score + gps_score, 1)

        entry["价值分"] = total_score
        entry["综合分"] = total_score
        entry["3km总用电"] = round(total_usage, 1)
        entry["3km平均电费"] = avg_price
        entry["gps热度"] = gps_heat

        site_dict = site.to_dict()
        site_dict["综合分"] = total_score
        site_dict["gps热度"] = gps_heat
        entry["站点"] = site_dict

        if entry["1km"]["total"] > 0:
            entry["最近档"] = "1km"
        elif entry["2km"]["total"] > 0:
            entry["最近档"] = "2km"
        else:
            entry["最近档"] = "3km"

        results.append(entry)

    return sorted(results, key=lambda x: x["综合分"], reverse=True)


def run_full_analysis(stations: list, cabinets: list, new_sites: list[NewSite] = None, gps_data: list = None) -> dict:
    task1 = analyze_selected_stations(stations, cabinets, gps_data)
    task2 = analyze_unselected_stations(stations, cabinets, gps_data)
    task3 = analyze_new_sites(new_sites or [], cabinets, gps_data)

    # 合并所有站点数据（包含综合分和GPS热度）
    all_stations_with_scores = []
    for item in task1:
        all_stations_with_scores.append(item["场站"])
    for item in task2:
        all_stations_with_scores.append(item["场站"])
    
    # 为未选站点添加综合分
    for station in stations:
        if station.selection_status == UNSELECTED_STATUS:
            matched = next((s for s in all_stations_with_scores if s["名称"] == station.name), None)
            if not matched:
                station_dict = station.to_dict()
                station_dict["综合分"] = 0
                station_dict["gps热度"] = 0
                all_stations_with_scores.append(station_dict)

    recommended_count = sum(1 for s in all_stations_with_scores if s.get("综合分", 0) >= 40 or s.get("是否选择") == "已选")
    other_count = len(all_stations_with_scores) - recommended_count

    return {
        "summary": {
            "total_stations": len(stations),
            "recommended_count": recommended_count,
            "other_count": other_count,
            "total_cabinets": len(cabinets),
            "new_sites_count": len(task3),
        },
        "all_stations": all_stations_with_scores,
        "all_cabinets": [c.to_dict() for c in cabinets],
        "all_new_sites": [s["站点"] for s in task3],
        "task1": task1,
        "task2": task2,
        "task3": task3,
    }
