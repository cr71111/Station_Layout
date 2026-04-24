#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Station_Layout.config.settings import (
    STATION_FILE,
    CABINET_FILE,
    NEW_SITES_FILE,
    GPS_FILE,
    ANALYSIS_JSON,
    GPS_JSON,
    REPORT_HTML,
)
from Station_Layout.src.data_loader import load_stations, load_cabinets, load_new_sites, load_gps_data
from Station_Layout.src.analyzer import run_full_analysis
from Station_Layout.src.report_builder import build_report, save_analysis_json
from Station_Layout.src.geo_utils import find_nearby_cabinets, find_nearby_cabinets_by_levels
from Station_Layout.config.settings import HIGH_LEVELS


def cluster_gps_for_heatmap(gps_data: list, grid_size: float = 0.006) -> list:
    """将GPS数据按网格聚类，每个网格只输出1个点，用count作为热力权重"""
    grid = {}
    for point in gps_data:
        gx = int(point["经度"] / grid_size)
        gy = int(point["纬度"] / grid_size)
        key = f"{gx}_{gy}"
        if key not in grid:
            grid[key] = {
                "lon": (gx + 0.5) * grid_size,
                "lat": (gy + 0.5) * grid_size,
                "count": 0,
                "orig_lon": point["经度"],
                "orig_lat": point["纬度"],
            }
        grid[key]["count"] += 1
        if grid[key]["count"] <= 3:
            grid[key]["orig_lon"] = point["经度"]
            grid[key]["orig_lat"] = point["纬度"]

    result = []
    for g in grid.values():
        result.append({
            "经度": g.get("orig_lon", g["lon"]),
            "纬度": g.get("orig_lat", g["lat"]),
            "_count": g["count"],
        })
    return result


def compute_tier_data(station, cabinets):
    """计算1km/2km/3km三层电柜数据"""
    tiers = {}
    for km in [1.0, 2.0, 3.0]:
        nearby = find_nearby_cabinets(station, cabinets, km)
        high_level = [c for c in nearby if c.get("等级") in HIGH_LEVELS]
        tiers[f"{int(km)}km"] = {
            "total": len(nearby),
            "high": len(high_level),
            "list": nearby[:10],
        }
    return tiers


def main():
    print("Loading data...")
    stations = load_stations(STATION_FILE)
    cabinets = load_cabinets(CABINET_FILE)
    new_sites = load_new_sites(NEW_SITES_FILE)
    gps_raw = load_gps_data(GPS_FILE)

    print(f"  Stations: {len(stations)}, Cabinets: {len(cabinets)}, New sites: {len(new_sites)}, GPS points: {len(gps_raw['all'])}")

    print("Running analysis...")
    analysis = run_full_analysis(stations, cabinets, new_sites, gps_raw['all'])

    # 预计算每个场站1km/2km/3km分层电柜数据
    print("Computing 1km/2km/3km tiered cabinets for all stations...")
    nearby_tiers = {}
    for station in stations:
        nearby_tiers[station.name] = compute_tier_data(station, cabinets)
    for site in new_sites:
        nearby_tiers[site.name] = compute_tier_data(site, cabinets)

    analysis['nearby_tiers'] = nearby_tiers

    # GPS聚类处理（减少数据量用于热力图）
    print("Clustering GPS data for heatmap visualization...")
    gps_all = cluster_gps_for_heatmap(gps_raw['all'])
    gps_driving = cluster_gps_for_heatmap(gps_raw['driving'])
    gps_parked = cluster_gps_for_heatmap(gps_raw['parked'])

    # 保存GPS数据到独立JSON文件
    gps_data = {
        'gps_all': gps_all,
        'gps_driving': gps_driving,
        'gps_parked': gps_parked,
    }
    with open(GPS_JSON, "w", encoding="utf-8") as f:
        json.dump(gps_data, f, ensure_ascii=False, indent=2)
    print(f"  GPS data saved: {GPS_JSON} ({len(gps_all)} points)")

    # 站点分析JSON不再包含GPS数据
    print(f"  Selected stations analyzed: {len(analysis['task1'])}")
    print(f"  Unselected candidates found: {len(analysis['task2'])}")
    print(f"  New sites analyzed: {len(analysis['task3'])}")

    print("Saving results...")
    save_analysis_json(analysis, ANALYSIS_JSON)
    print(f"  Analysis JSON saved: {ANALYSIS_JSON}")

    build_report(analysis, REPORT_HTML)
    print(f"  Report saved: {REPORT_HTML}")

    print("\nTop 5 unselected candidates:")
    for item in analysis["task2"][:5]:
        s = item["场站"]
        t1 = item.get("1km", {})
        t2 = item.get("2km", {})
        t3 = item.get("3km", {})
        print(f"  {s['名称']} | 1km:{t1.get('total',0)}({t1.get('high',0)}高) 2km:{t2.get('total',0)}({t2.get('high',0)}高) 3km:{t3.get('total',0)}({t3.get('high',0)}高) Score:{item.get('价值分',0)}")

    print("\nDone.")


if __name__ == "__main__":
    main()
