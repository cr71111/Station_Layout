import json, math, os, csv

DATA_DIR = 'docs/data'
os.makedirs(DATA_DIR, exist_ok=True)

# ========== 1. 从CSV提取GPS数据 ==========
gps_all = []
gps_driving = []
gps_parked = []

with open('data/用户GPS位置.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        try:
            lat = float(row['纬度'])
            lng = float(row['经度'])
            state = row.get('行驶状态', '').strip()
            pt = {'纬度': lat, '经度': lng}
            gps_all.append(pt)
            if state == '行驶':
                gps_driving.append(pt)
            elif state == '停车':
                gps_parked.append(pt)
        except (ValueError, KeyError):
            continue

print(f"GPS: 全部={len(gps_all)}, 行驶={len(gps_driving)}, 停车={len(gps_parked)}")

# 保存GPS JSON
with open(f'{DATA_DIR}/gps_all.json', 'w', encoding='utf-8') as f:
    json.dump(gps_all, f, ensure_ascii=False)
with open(f'{DATA_DIR}/gps_driving.json', 'w', encoding='utf-8') as f:
    json.dump(gps_driving, f, ensure_ascii=False)
with open(f'{DATA_DIR}/gps_parked.json', 'w', encoding='utf-8') as f:
    json.dump(gps_parked, f, ensure_ascii=False)
print("GPS JSON saved")

# ========== 2. 读取场站和电柜数据 ==========
with open('docs/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 优先从data.json读取（如果存在且有效）
stations, cabinets, new_sites = None, None, None
if os.path.exists(f'{DATA_DIR}/data.json'):
    try:
        with open(f'{DATA_DIR}/data.json', 'r', encoding='utf-8') as f:
            cached = json.load(f)
            stations = cached.get('all_stations')
            cabinets = cached.get('all_cabinets')
            new_sites = cached.get('all_new_sites', [])
        print(f"Loaded from data.json: {len(stations)} stations")
    except:
        pass

# 如果data.json无效，从HTML提取
if not stations:
    data_start = content.find('const DATA=Object.assign(')
    if data_start > 0:
        data_end = content.find('\nlet map, heatmapLayer', data_start)
        data_str = content[data_start + len('const DATA=Object.assign('):data_end].rstrip().rstrip(';')
        depth = 0; obj_start = -1
        for i, ch in enumerate(data_str):
            if ch == '{' and depth == 0: obj_start = i; depth += 1
            elif ch == '{': depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0: data = json.loads(data_str[obj_start:i+1]); break
        stations = data['all_stations']
        cabinets = data['all_cabinets']
        new_sites = data.get('all_new_sites', [])
        print(f"Extracted from HTML: {len(stations)} stations")

# 保存场站和电柜JSON
with open(f'{DATA_DIR}/stations.json', 'w', encoding='utf-8') as f:
    json.dump(stations, f, ensure_ascii=False)
with open(f'{DATA_DIR}/cabinets.json', 'w', encoding='utf-8') as f:
    json.dump(cabinets, f, ensure_ascii=False)
if new_sites:
    with open(f'{DATA_DIR}/new_sites.json', 'w', encoding='utf-8') as f:
        json.dump(new_sites, f, ensure_ascii=False)
print(f"Stations: {len(stations)}, Cabinets: {len(cabinets)}, NewSites: {len(new_sites)}")

# ========== 3. 计算综合分 ==========
cab_list = []
for c in cabinets:
    cab_list.append({
        'lat': c['纬度'], 'lng': c['经度'], 'level': c['等级'],
        'price': float(c['电费单价'] or 0), 'usage': float(c['用电度数'] or 0),
        'brand': c['品牌'], 'site': c['站点'], 'id': c['ID'],
        'lat_raw': c['纬度'], 'lng_raw': c['经度']
    })

def haversine(lat1, lng1, lat2, lng2):
    R = 6371000
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def get_cabs(slat, slng, r):
    result = []
    for c in cab_list:
        d = haversine(slat, slng, c['lat'], c['lng'])
        if d <= r:
            c2 = dict(c); c2['dist_km'] = round(d / 1000, 2)
            result.append(c2)
    return sorted(result, key=lambda x: x['dist_km'])

LW = {'特高': 5, '高': 4, '中高': 3, '中': 2, '低': 1}
max_gps = max((float(s.get('gps热度', 0)) for s in stations), default=1)

def calc_score(s):
    slat, slng = s['纬度'], s['经度']
    gh = float(s.get('gps热度', 0))
    c1 = get_cabs(slat, slng, 1000)
    c2 = get_cabs(slat, slng, 2000)
    c3 = get_cabs(slat, slng, 3000)

    # GPS热度分 (max 50)
    gps_s = min(50, (gh / max_gps) * 50) if max_gps > 0 else 0

    # ===== 关键修复：3km内无电柜则其他维度全部为0 =====
    if not c3:
        return {
            'total': round(gps_s, 1),
            'gps_score': round(gps_s, 1), 'dist_score': 0,
            'price_score': 0, 'usage_score': 0, 'level_score': 0,
            'tier_info': {
                '1km': {'total': 0, 'high': 0, 'list': []},
                '2km': {'total': 0, 'high': 0, 'list': []},
                '3km': {'total': 0, 'high': 0, 'list': []}
            }
        }

    # 距离竞争分 (max 30) — 近处高等级电柜扣分，远处有bonus
    pen = sum(LW.get(c['level'], 1) * 2 for c in c1) + sum(LW.get(c['level'], 1) * 0.5 for c in c2 if c not in c1)
    t3 = len(c3)
    bonus = 20 if t3 <= 5 else (10 if t3 <= 10 else (5 if t3 <= 15 else 0))
    dist_s = max(0, 30 - pen * 0.5 + bonus)

    # 电费单价分 (max 25) — 单价越高分越高
    price_s = min(25, sum(c['price'] for c in c3) / len(c3) * 18)

    # 用电量分 (max 25) — 用电越大分越高
    usage_s = min(25, sum(c['usage'] for c in c3) / 3000)

    # 等级分 (max 20) — 等级越高分越大
    level_s = min(20, sum(LW.get(c['level'], 1) * 1.5 for c in c3))

    total = round(gps_s + dist_s + price_s + usage_s + level_s, 1)

    def mk(cabs):
        return [{'品牌': c['brand'], '站点': c['site'], '等级': c['level'],
                 '电费单价': str(c['price']), '用电度数': str(round(c['usage'], 1)),
                 '距离km': str(c['dist_km'])} for c in cabs]

    return {
        'total': total,
        'gps_score': round(gps_s, 1), 'dist_score': round(dist_s, 1),
        'price_score': round(price_s, 1), 'usage_score': round(usage_s, 1),
        'level_score': round(level_s, 1),
        'tier_info': {
            '1km': {'total': len(c1), 'high': sum(1 for c in c1 if c['level'] in ('特高', '高')), 'list': mk(c1)},
            '2km': {'total': len(c2), 'high': sum(1 for c in c2 if c['level'] in ('特高', '高')), 'list': mk(c2)},
            '3km': {'total': len(c3), 'high': sum(1 for c in c3 if c['level'] in ('特高', '高')), 'list': mk(c3)}
        }
    }

score_results = {}
for s in stations:
    sr = calc_score(s); score_results[s['名称']] = sr; s['综合分'] = sr['total']
for s in new_sites:
    sr = calc_score(s); score_results[s['名称']] = sr; s['综合分'] = sr['total']

nearby_tiers = {}; score_details = {}
for n, sr in score_results.items():
    nearby_tiers[n] = sr['tier_info']
    score_details[n] = {k: sr[k] for k in ['total', 'gps_score', 'dist_score', 'price_score', 'usage_score', 'level_score']}

# 推荐：已选 + 综合分>=前30% + GPS热度>=65%最高值
rec_names = set()
scores_sorted = sorted([s['综合分'] for s in stations], reverse=True)
p70 = scores_sorted[int(len(scores_sorted) * 0.3)] if len(scores_sorted) > 0 else 70
for s in stations:
    if s.get('是否选择') == '已选' or s['综合分'] >= p70:
        rec_names.add(s['名称'])
    elif float(s.get('gps热度', 0)) >= max_gps * 0.65:
        rec_names.add(s['名称'])

summary = {
    'total_stations': len(stations),
    'recommended_count': len(rec_names),
    'other_count': len(stations) - len(rec_names),
    'total_cabinets': len(cabinets),
    'new_sites_count': len(new_sites)
}

new_data = {
    'summary': summary,
    'all_stations': stations,
    'all_cabinets': cabinets,
    'nearby_tiers': nearby_tiers,
    'all_new_sites': new_sites,
    'score_details': score_details
}

# 保存主数据JSON（不含GPS）
with open(f'{DATA_DIR}/data.json', 'w', encoding='utf-8') as f:
    json.dump(new_data, f, ensure_ascii=False)
with open(f'{DATA_DIR}/nearby_tiers.json', 'w', encoding='utf-8') as f:
    json.dump(nearby_tiers, f, ensure_ascii=False)
with open(f'{DATA_DIR}/score_details.json', 'w', encoding='utf-8') as f:
    json.dump(score_details, f, ensure_ascii=False)

print(f"\nRec: {len(rec_names)}, Other: {len(stations) - len(rec_names)}, Threshold: {p70}")
for s in sorted(stations, key=lambda x: -x['综合分'])[:10]:
    sd = score_results[s['名称']]
    print(f"  {s['名称']}: {sd['total']} (GPS:{sd['gps_score']} 距:{sd['dist_score']} 电费:{sd['price_score']} 用电:{sd['usage_score']} 等级:{sd['level_score']})")

# ========== 4. 生成新的HTML（外部加载JSON）==========
html_before_script = content[:content.find('<script>')]

# 确保图例有中低电柜
if '中低/低电柜' not in html_before_script:
    html_before_script = html_before_script.replace(
        '<div class="legend-item"><div class="legend-dot" style="background:#22c55e"></div>中等级电柜</div>',
        '<div class="legend-item"><div class="legend-dot" style="background:#22c55e"></div>中等级电柜</div>\n      <div class="legend-item"><div class="legend-dot" style="background:#94a3b8"></div>中低/低电柜</div>'
    )
if '其他场站' in html_before_script and '#f59e0b' not in html_before_script.split('其他场站')[0][-50:]:
    html_before_script = html_before_script.replace(
        '<div class="legend-item"><div class="legend-dot" style="background:#94a3b8"></div>其他场站</div>',
        '<div class="legend-item"><div class="legend-dot" style="background:#f59e0b"></div>其他场站</div>'
    )

js_code = '''<script>
let map, heatmapLayer, circleLayers=[], cabinetLabels=[], DATA=null;

function levelColor(lv){
  if(lv==='特高'||lv==='高') return '#ef4444';
  if(lv==='中高') return '#f59e0b';
  if(lv==='中') return '#22c55e';
  return '#94a3b8';
}
function getScoreColor(score){
  if(score>=100) return '#dc2626';
  if(score>=80) return '#f97316';
  if(score>=60) return '#eab308';
  if(score>=40) return '#22c55e';
  return '#94a3b8';
}
function clearSelection(){
  circleLayers.forEach(l=>map.removeLayer(l));
  circleLayers=[];
  cabinetLabels.forEach(l=>map.removeLayer(l));
  cabinetLabels=[];
  document.getElementById('btnClear').style.display='none';
  document.getElementById('circleInfo').style.display='none';
  map.flyTo([30.65,104.07],11,{duration:0.8});
}
function flyToWithCircles(lon,lat,name){
  circleLayers.forEach(l=>map.removeLayer(l));
  circleLayers=[];
  cabinetLabels.forEach(l=>map.removeLayer(l));
  cabinetLabels=[];
  map.flyTo([lat,lon],13,{duration:0.8});
  const colors=['#ef4444','#f59e0b','#22c55e'];
  const radii=[1000,2000,3000];
  radii.forEach((r,i)=>{
    const c=L.circle([lat,lon],{radius:r,color:colors[i],weight:2,fillColor:colors[i],fillOpacity:0.06+i*0.03,dashArray:i===0?'':'8 4'}).addTo(map);
    circleLayers.push(c);
  });
  document.getElementById('btnClear').style.display='inline-block';
  document.getElementById('circleInfo').innerHTML='<span style="color:#ef4444">●</span>1km <span style="color:#f59e0b">●</span>2km <span style="color:#22c55e">●</span>3km 范围圈';
  document.getElementById('circleInfo').style.display='block';
  showCabinetLabels(name);
}
function showCabinetLabels(stationName){
  const tier=DATA.nearby_tiers[stationName];
  if(!tier)return;
  const allCabs=[...(tier['3km'].list||[])];
  allCabs.forEach(c=>{
    const cab=(DATA.all_cabinets||[]).find(x=>x['站点']===c['站点']);
    if(!cab)return;
    const col=levelColor(cab['等级']);
    const icon=L.divIcon({
      html:`<div style="background:${col};color:white;padding:2px 5px;border-radius:4px;font-size:10px;font-weight:700;white-space:nowrap;box-shadow:0 1px 4px rgba(0,0,0,.3);border:1px solid white">${cab['等级']}</div>`,
      className:'',iconSize:[30,16],iconAnchor:[15,8]
    });
    const m=L.marker([cab['纬度'],cab['经度']],{icon}).addTo(map);
    m.bindPopup(`<b>${cab['品牌']} · ${cab['站点']}</b><br>等级:<b style="color:${col}">${cab['等级']}</b><br>电费:${cab['电费单价']}元/度 · 用电:${cab['用电度数']}度<br>日均换电:${cab['日均换电']}次/仓 · 仓数:${cab['仓数']}`);
    cabinetLabels.push(m);
  });
}
function updateStats(){
  if(!DATA)return;
  document.getElementById('s1').textContent=DATA.summary.total_stations;
  document.getElementById('s2').textContent=DATA.summary.recommended_count||0;
  document.getElementById('s3').textContent=DATA.summary.other_count||0;
  document.getElementById('s4').textContent=DATA.summary.total_cabinets;
}
function getStatusBadge(s){
  if(s['是否选择']==='已选') return '<span class="badge badge-recommended">已选</span>';
  if((s['综合分']||0)>0) return '<span class="badge badge-recommended">推荐</span>';
  return '<span class="badge badge-other">其他</span>';
}
function buildExplain(s,t1,t2,t3){
  const score=s['综合分']||0;
  const isSelected=s['是否选择']==='已选';
  const sd=DATA.score_details?DATA.score_details[s['名称']]:null;
  if(isSelected){
    const parts=[];
    if(sd){parts.push(`热度${sd.gps_score}`);parts.push(`距离${sd.dist_score}`);parts.push(`电费${sd.price_score}`);parts.push(`用电${sd.usage_score}`);parts.push(`等级${sd.level_score}`);}
    return `<div class="score-explain"><b>✓ 已选场站</b> — <b>${score.toFixed(1)}</b>分 = ${parts.join(' + ')}分。1km内${t1.total}柜(${t1.high}高)、2km内${t2.total}柜(${t2.high}高)、3km内${t3.total}柜(${t3.high}高)</div>`;
  }
  if(sd&&sd.total>0){
    const parts=[];
    parts.push(`热度${sd.gps_score}`);parts.push(`距离${sd.dist_score}`);
    parts.push(`电费${sd.price_score}`);parts.push(`用电${sd.usage_score}`);parts.push(`等级${sd.level_score}`);
    return `<div class="score-explain"><b>✓ 推荐布局</b> — <b>${score.toFixed(1)}</b>分 = ${parts.join(' + ')}分。1km内${t1.total}柜(${t1.high}高)、2km内${t2.total}柜(${t2.high}高)、3km内${t3.total}柜(${t3.high}高)</div>`;
  }
  return `<div class="score-explain"><b>待观察</b> — 暂无评分。3km内${t3.total}柜(${t3.high}高等级)</div>`;
}
function renderAllStations(filter){
  if(!DATA)return;
  const el=document.getElementById('stationList');
  let allStations=DATA.all_stations||[];
  let newSites=DATA.all_new_sites||[];
  let stations=[];
  if(filter==='recommended'){
    stations=allStations.filter(s=>s['是否选择']==='已选'||(s['综合分']||0)>0);
    newSites.filter(s=>(s['综合分']||0)>0).forEach(s=>stations.push(s));
    stations.sort((a,b)=>(b['综合分']||0)-(a['综合分']||0));
  } else {
    stations=allStations.filter(s=>s['是否选择']!=='已选'&&(s['综合分']||0)<=0);
    newSites.filter(s=>(s['综合分']||0)<=0).forEach(s=>stations.push(s));
  }
  document.getElementById('stationCount').textContent='共 '+stations.length+' 个场站';
  let h='';
  stations.forEach((s,idx)=>{
    const isRec=s['是否选择']==='已选'||(s['综合分']||0)>0;
    const headClass=isRec?'recommended':'other';
    const score=s['综合分']||0;
    const tierData=DATA.nearby_tiers?DATA.nearby_tiers[s['名称']]:null;
    const t1=tierData?tierData['1km']:{total:0,high:0,list:[]};
    const t2=tierData?tierData['2km']:{total:0,high:0,list:[]};
    const t3=tierData?tierData['3km']:{total:0,high:0,list:[]};
    h+=`<div class="station-card" onclick="flyToWithCircles(${s['经度']},${s['纬度']},'${s['名称']}')">
      <div class="station-head ${headClass}">
        <div><div class="station-name"><span style="color:#94a3b8;font-size:11px;margin-right:4px">${String(idx+1).padStart(2,'0')}</span>${s['名称']}</div>
        <div class="station-meta">${s['地区']||s['地址']||''} · ${s['属性']||''} · 终端${s['终端数']||'-'}个</div></div>
        ${getStatusBadge(s)}
      </div>
      <div class="score-bar">
        <div class="score-track"><div class="score-fill" style="width:${Math.min(score,150)}%;background:${getScoreColor(score)}"></div></div>
        <div class="score-val">${score.toFixed(1)}</div>
      </div>
      ${buildExplain(s,t1,t2,t3)}
      <div class="tier-row">
        <div class="tier-badge ${t1.total>0?'tier-1km':'tier-0'}" onclick="event.stopPropagation();flyToTier('${s['名称']}',1)">1km · <b>${t1.total}</b>柜(${t1.high}高)</div>
        <div class="tier-badge ${t2.total>t1.total?'tier-2km':(t2.total>0?'tier-1km':'tier-0')}" onclick="event.stopPropagation();flyToTier('${s['名称']}',2)">2km · <b>${t2.total}</b>柜(${t2.high}高)</div>
        <div class="tier-badge ${t3.total>t2.total?'tier-3km':(t3.total>0?'tier-2km':'tier-0')}" onclick="event.stopPropagation();flyToTier('${s['名称']}',3)">3km · <b>${t3.total}</b>柜(${t3.high}高)</div>
      </div>`;
    const allCabs=[...(t3.list||[])];
    if(allCabs.length>0){
      h+=`<div class="cabinet-list">`;
      allCabs.forEach(c=>{
        h+=`<div class="cabinet-item">
          <div class="dot" style="background:${levelColor(c['等级'])}"></div>
          <span class="cab-name">${c['品牌']}·${c['站点'].substring(0,10)}</span>
          <span class="cab-level" style="color:${levelColor(c['等级'])}">${c['等级']}</span>
          <span class="cab-price">${c['电费单价']}元</span>
          <span class="cab-usage">${c['用电度数']}度</span>
          <span class="cab-dist">${c['距离km']}km</span>
        </div>`});
      h+=`</div>`;
    } else {
      h+=`<div class="cabinet-list"><div style="text-align:center;padding:10px;color:#9ca3af;font-size:12px;background:#f9fafb;border-radius:8px">3km内暂无电柜</div></div>`;
    }
    h+=`</div>`;
  });
  el.innerHTML=h;
}
function flyToTier(name,tier){
  const s=(DATA.all_stations||[]).find(x=>x['名称']===name)||(DATA.all_new_sites||[]).find(x=>x['名称']===name);
  if(!s)return;
  flyToWithCircles(s['经度'],s['纬度'],name);
}

function buildHeatData(points){
  if(!points||points.length===0) return [];
  return points.map(p=>[p['纬度'],p['经度'],1]);
}

let currentGPS = { all: [], driving: [], parked: [] };

async function loadAllData(){
  try {
    const [dataRes, gpsAllRes, gpsDrivingRes, gpsParkedRes] = await Promise.all([
      fetch('data/data.json').then(r=>r.json()),
      fetch('data/gps_all.json').then(r=>r.json()),
      fetch('data/gps_driving.json').then(r=>r.json()),
      fetch('data/gps_parked.json').then(r=>r.json())
    ]);
    DATA = dataRes;
    currentGPS.all = gpsAllRes;
    currentGPS.driving = gpsDrivingRes;
    currentGPS.parked = gpsParkedRes;
    console.log(`Data loaded: ${DATA.all_stations.length} stations, ${currentGPS.all.length} GPS points`);
    updateStats();
    renderAllStations('recommended');
    initMap();
  } catch(err){
    console.error('Load error:', err);
    document.getElementById('stationList').innerHTML='<div style="padding:40px;text-align:center;color:#ef4444">数据加载失败，请检查网络连接</div>';
  }
}

function setHeatmap(type){
  document.querySelectorAll('.heatmap-btn').forEach(b=>b.classList.remove('active'));
  event.target.classList.add('active');
  if(!heatmapLayer) return;
  map.removeLayer(heatmapLayer);
  let points=[];
  if(type==='all') points=currentGPS.all;
  else if(type==='driving') points=currentGPS.driving;
  else if(type==='parked') points=currentGPS.parked;
  const hd=buildHeatData(points);
  heatmapLayer=L.heatLayer(hd,{
    radius:28,blur:16,maxZoom:16,
    max:12,
    gradient:{0.0:'#2563eb',0.2:'#06b6d4',0.4:'#22c55e',0.6:'#eab308',0.8:'#f97316',1.0:'#dc2626'}
  }).addTo(map);
  applyZoomRadius();
}

function applyZoomRadius(){
  if(!heatmapLayer) return;
  const z = map.getZoom();
  const lat = map.getCenter().lat;
  // 缩小(低zoom)→大半径+高max=颜色浓烈看整体；放大(高zoom)→极小半径+极低max=清晰看局部
  const geoRadius = z < 12 ? 450 : z < 13 ? 350 : z < 14 ? 250 : z < 15 ? 170 : z < 16 ? 110 : 60;
  const metersPerPx = 156543.03392 * Math.cos(lat * Math.PI / 180) / Math.pow(2, z);
  const rawR = geoRadius / metersPerPx;
  const r = Math.min(Math.max(Math.round(rawR), 5), 80);
  const b = Math.max(Math.round(r * 0.4), 2);
  // 关键：zoom越大(越放大) → max越小 → 颜色越淡越清晰
  const maxVal = z < 11 ? 18 : z < 12 ? 14 : z < 13 ? 10 : z < 14 ? 6 : z < 15 ? 3.5 : z < 16 ? 2 : 1.2;
  heatmapLayer.setOptions({radius: r, blur: b, max: maxVal});
}

function initMap(){
  if(!DATA)return;
  map=L.map('mapDiv',{center:[30.65,104.07],zoom:11});
  L.tileLayer('https://webrd04.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}',{attribution:'© 高德地图',maxZoom:18,opacity:.70}).addTo(map);

  const hd=buildHeatData(currentGPS.all);
  heatmapLayer=L.heatLayer(hd,{
    radius:28,blur:16,maxZoom:16,
    max:12,
    gradient:{0.0:'#2563eb',0.2:'#06b6d4',0.4:'#22c55e',0.6:'#eab308',0.8:'#f97316',1.0:'#dc2626'}
  }).addTo(map);
  applyZoomRadius();
  map.on('zoomend',applyZoomRadius);

  DATA.all_cabinets.forEach(c=>{
    const col=levelColor(c['等级']);
    const r=(c['等级']==='特高'||c['等级']==='高')?10:(c['等级']==='中高'?8:6);
    L.circleMarker([c['纬度'],c['经度']],{radius:r+3,color:'#ffffff',weight:1,fillColor:'#ffffff',fillOpacity:1}).addTo(map);
    L.circleMarker([c['纬度'],c['经度']],{radius:r,color:col,weight:1.5,fillColor:col,fillOpacity:.9})
      .addTo(map)
      .bindPopup(`<b>${c['品牌']} · ${c['站点']}</b><br>等级: <b style="color:${col}">${c['等级']}</b><br>电费: ${c['电费单价']}元/度 · 用电: ${c['用电度数']}度<br>日均换电: ${c['日均换电']} 次/仓 · 仓数: ${c['仓数']}`);
  });

  DATA.all_stations.forEach(s=>{
    const isRec=s['是否选择']==='已选'||(s['综合分']||0)>0;
    const col=isRec?'#1d4ed8':'#f59e0b';
    const sz=isRec?22:16;
    const icon=L.divIcon({
      html:`<div style="width:${sz+4}px;height:${sz+4}px;background:white;border-radius:50%;display:flex;align-items:center;justify-content:center;box-shadow:0 2px 8px rgba(0,0,0,.35)">
        <div style="width:${sz}px;height:${sz}px;background:${col};border:3px solid white;border-radius:50%"></div>
      </div>`,
      className:'',iconSize:[sz+4,sz+4],iconAnchor:[(sz+4)/2,(sz+4)/2]
    });
    L.marker([s['纬度'],s['经度']],{icon})
      .addTo(map)
      .on('click',()=>flyToWithCircles(s['经度'],s['纬度'],s['名称']))
      .bindPopup(`<b>${s['名称']}</b><br><span style="color:${col};font-weight:600">${isRec?'推荐站点':'其他站点'}</span> · ${s['地区']}<br>综合分: ${s['综合分']||0}<br>类型: ${s['属性']} · 终端: ${s['终端数']}个`);
  });

  (DATA.all_new_sites||[]).forEach(s=>{
    const isRec=(s['综合分']||0)>0;
    const col=isRec?'#10b981':'#f59e0b';
    const sz=isRec?18:14;
    const icon=L.divIcon({
      html:`<div style="width:${sz+4}px;height:${sz+4}px;background:white;border-radius:50%;display:flex;align-items:center;justify-content:center;box-shadow:0 2px 8px rgba(0,0,0,.35)">
        <div style="width:${sz}px;height:${sz}px;background:${col};border:3px solid white;border-radius:50%"></div>
      </div>`,
      className:'',iconSize:[sz+4,sz+4],iconAnchor:[(sz+4)/2,(sz+4)/2]
    });
    L.marker([s['纬度'],s['经度']],{icon})
      .addTo(map)
      .on('click',()=>flyToWithCircles(s['经度'],s['纬度'],s['名称']))
      .bindPopup(`<b>${s['名称']}</b><br><span style="color:${col};font-weight:600">${isRec?'推荐新址':'待观察'}</span><br>综合分: ${s['综合分']||0}<br>${s['地址']}`);
  });
}

window.addEventListener('load',()=>{
  document.getElementById('stationList').innerHTML='<div style="padding:40px;text-align:center;color:#64748b"><div style="font-size:24px;margin-bottom:10px">⏳</div>正在加载数据...</div>';
  loadAllData();
});

</script>
</body>
</html>'''

final_html = html_before_script + js_code

with open('docs/index.html', 'w', encoding='utf-8') as f:
    f.write(final_html)

print(f"\nHTML written! Size: {len(final_html)} chars")
print(f"   GPS data loaded from CSV via external JSON files")
