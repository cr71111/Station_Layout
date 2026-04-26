# 换电站点布局分析

## 项目简介

基于 GPS 热力数据、现有电柜分布和综合评分算法，分析成都市换电站点的最优布局方案。

## 项目结构

```
Station_Layout/
├── data/                    # 原始数据源
│   ├── 用户GPS位置.csv
│   ├── 自营场站列表2026.3.4_带经纬度.csv
│   ├── 现有电柜站点.csv
│   └── 新增站点.txt
├── docs/                    # GitHub Pages 部署目录
│   ├── index.html           # 主页面（Mapbox GL JS 地图）
│   ├── algorithm.html       # 算法说明页
│   └── data/                # JSON 数据文件
│       ├── data.json        # 场站+电柜主数据
│       ├── gps_all.json     # 全部 GPS 数据
│       ├── gps_driving.json # 行驶状态 GPS
│       ├── gps_parked.json  # 停车状态 GPS
│       ├── nearby_tiers.json
│       ├── score_details.json
│       ├── stations.json
│       ├── cabinets.json
│       └── new_sites.json
├── src/                     # 数据处理脚本
│   └── rebuild.py           # 主脚本：数据提取、评分计算、JSON 生成
└── temp/                    # 旧版脚本归档（已废弃）
```

## 使用方法

### 1. 运行数据处理脚本

```bash
cd d:\PY代码\换电站点布局分析\Station_Layout
python src/rebuild.py
```

脚本会自动：
- 从 CSV 提取 GPS 数据并保存为 JSON
- 读取场站和电柜数据
- 计算每个场站的综合评分（GPS热度分 + 距离分 + 电费分 + 用电分 + 等级分）
- 生成 `docs/data/` 下的所有 JSON 数据文件

### 2. 查看网页

直接打开 `docs/index.html` 或部署到 GitHub Pages：
- 主页面：地图可视化、场站列表、热力图切换
- 算法说明：`docs/algorithm.html`

## 综合评分算法

| 维度 | 满分 | 说明 |
|------|------|------|
| GPS 热度分 | 50 | 场站周边 GPS 点位密度 |
| 距离竞争分 | 30 | 周边电柜距离和等级竞争 |
| 电费单价分 | 25 | 周边电费单价越高，替换后节省成本越多 |
| 用电量分 | 25 | 周边电柜用电量越大，需求越高 |
| 等级分 | 20 | 周边电柜等级越高，竞争越激烈 |

## 技术栈

- **前端**: Mapbox GL JS, HTML/CSS/JavaScript
- **数据处理**: Python
- **部署**: GitHub Pages
