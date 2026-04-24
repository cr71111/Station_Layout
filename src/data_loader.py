#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import csv
import re
from Station_Layout.src.models import Station, Cabinet, NewSite
from Station_Layout.config.settings import CABINET_COORDINATE_BOUNDS


def load_stations(filepath: str) -> list[Station]:
    rows = []
    with open(filepath, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                lon = float(row["经度"])
                lat = float(row["纬度"])
                if lon and lat:
                    rows.append(
                        Station(
                            name=row["电站名称"].strip(),
                            city=row["归属城市"].strip(),
                            district=row["归属地区"].strip(),
                            address=row["电站地址"].strip(),
                            terminal_count=row["电站终端数"].strip(),
                            attribute=row["电站属性"].strip(),
                            selection_status=row["是否选择"].strip(),
                            longitude=lon,
                            latitude=lat,
                        )
                    )
            except (ValueError, KeyError):
                continue
    return rows


def load_cabinets(filepath: str) -> list[Cabinet]:
    bounds = CABINET_COORDINATE_BOUNDS
    rows = []
    with open(filepath, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                lon = float(row["经度"])
                lat = float(row["纬度"])
                if lon and lat and bounds["lon_min"] < lon < bounds["lon_max"] and bounds["lat_min"] < lat < bounds["lat_max"]:
                    rows.append(
                        Cabinet(
                            brand=row["换电柜品牌"].strip(),
                            site_name=row["换电站点"].strip(),
                            cabinet_id=row["电柜id"].strip(),
                            slot_count=row["电柜仓数"].strip(),
                            longitude=lon,
                            latitude=lat,
                            daily_swaps=row.get("单仓换电次数", "").strip(),
                            level=row.get("电柜等级", "").strip(),
                            electricity_price=row.get("电费单价", "").strip(),
                            electricity_usage=row.get("用电度数", "").strip(),
                        )
                    )
            except (ValueError, KeyError):
                continue
    return rows


def load_new_sites(filepath: str) -> list[NewSite]:
    sites = []
    pattern = re.compile(r"站点\d+：(.*?),(.*?)[，,]经度([\d.]+),纬度([\d.]+)")
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            m = pattern.search(line)
            if m:
                sites.append(
                    NewSite(
                        name=m.group(1),
                        address=m.group(2),
                        longitude=float(m.group(3)),
                        latitude=float(m.group(4)),
                    )
                )
    return sites


def load_gps_data(filepath: str) -> dict:
    gps_all = []
    gps_driving = []
    gps_parked = []
    
    with open(filepath, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                lon = float(row["经度"])
                lat = float(row["纬度"])
                status = row.get("行驶状态", "").strip()
                
                point = {
                    "经度": lon,
                    "纬度": lat,
                    "行驶状态": status,
                    "行驶距离_米": row.get("行驶距离_米", "0").strip(),
                    "停留时长_秒": row.get("停留时长_秒", "0").strip(),
                }
                
                gps_all.append(point)
                
                if status == "行驶":
                    gps_driving.append(point)
                elif status in ["停车", "起点"]:
                    gps_parked.append(point)
                    
            except (ValueError, KeyError):
                continue
    
    return {
        "all": gps_all,
        "driving": gps_driving,
        "parked": gps_parked,
    }
