#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

STATION_FILE = os.path.join(DATA_DIR, "自营场站列表2026.3.4_带经纬度.csv")
CABINET_FILE = os.path.join(DATA_DIR, "现有电柜站点.csv")
NEW_SITES_FILE = os.path.join(DATA_DIR, "新增站点.txt")
GPS_FILE = os.path.join(DATA_DIR, "用户GPS位置.csv")

ANALYSIS_JSON = os.path.join(OUTPUT_DIR, "station_analysis.json")
GPS_JSON = os.path.join(OUTPUT_DIR, "gps_data.json")
REPORT_HTML = os.path.join(OUTPUT_DIR, "station_report.html")

SELECTED_STATUS = "已选"
UNSELECTED_STATUS = "未选"

PROXIMITY_THRESHOLDS = [1.0, 2.0, 3.0]

VALUE_SCORE_WEIGHTS = {
    "1km_high": 6,
    "1km_total": 3,
    "2km_high": 2,
    "2km_total": 1,
    "3km_high": 1,
}

CABINET_COORDINATE_BOUNDS = {"lon_min": 70, "lon_max": 140, "lat_min": 15, "lat_max": 55}

HIGH_LEVELS = {"高", "特高", "中高"}

MAP_CENTER = {"lat": 30.65, "lon": 104.07}
MAP_DEFAULT_ZOOM = 11
