#!/usr/bin/env python3
from pathlib import Path
import json
import re
import pandas as pd
import requests
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
DATA = DOCS / "data"
URL = "https://sbti.unun.dev/"


def extract_dim_question_map(html: str):
    qmap = {}
    start = html.find("const questions = [")
    if start == -1:
        return qmap
    sub = html[start:]
    i = sub.find("[")
    cnt = 0
    end = None
    for j, ch in enumerate(sub[i:], start=i):
        if ch == "[":
            cnt += 1
        elif ch == "]":
            cnt -= 1
            if cnt == 0:
                end = j
                break
    if end is None:
        return qmap
    block = sub[i:end + 1]
    pat = re.compile(r"id:\s*'([^']+)'\s*,\s*dim:\s*'([^']+)'\s*,\s*text:\s*'((?:\\\\'|[^'])*)'", re.S)
    for qid, dim, text in pat.findall(block):
        text = text.replace("\\'", "'").strip()
        qmap.setdefault(dim, []).append({"id": qid, "text": text})
    return qmap


def main():
    required = [
        DATA / "summary.json",
        DATA / "type_distribution_full.csv",
        DATA / "type_meta.csv",
        DATA / "type_images.json",
    ]
    for p in required:
        if not p.exists():
            raise FileNotFoundError(f"Missing required file: {p}")

    summary = json.loads((DATA / "summary.json").read_text(encoding="utf-8"))
    full = pd.read_csv(DATA / "type_distribution_full.csv")
    meta = pd.read_csv(DATA / "type_meta.csv")
    images = json.loads((DATA / "type_images.json").read_text(encoding="utf-8"))

    cn_map = dict(zip(meta["code"], meta["cn"]))
    full["cn"] = full["type"].map(cn_map).fillna("")
    full["label"] = full.apply(lambda r: f"{r['type']}（{r['cn']}）" if r['cn'] else r['type'], axis=1)

    def normalize_image(src):
        if not src:
            return None
        s = str(src)
        if s.startswith("./image/"):
            return "https://sbti.unun.dev/" + s[2:]
        return s

    cards = []
    for r in full.to_dict(orient="records"):
        cards.append({
            "code": r["type"],
            "cn": r["cn"],
            "share": round(float(r["percentage"]), 4),
            "image": normalize_image(images.get(r["type"])),
        })
    cards = sorted(cards, key=lambda x: -x["share"])

    level_num = {"L": 1, "M": 2, "H": 3}
    pattern_rows = []
    for r in meta.to_dict(orient="records"):
        pattern = str(r.get("pattern", ""))
        chars = [c for c in pattern.replace("-", "") if c in "LMH"]
        if len(chars) == 15:
            pattern_rows.append({
                "code": r.get("code", ""),
                "cn": r.get("cn", ""),
                "pattern": pattern,
                "vec": [level_num[c] for c in chars],
            })

    # pull exact question mapping (q1..q30) from public page
    qmap = {}
    try:
        page_html = requests.get(URL, timeout=30).text
        qmap = extract_dim_question_map(page_html)
    except Exception:
        qmap = {}

    base_defs = [
        {"id": "S1", "name": "S1 自尊自信", "desc": "与自我价值感和自我评价有关"},
        {"id": "S2", "name": "S2 自我清晰度", "desc": "与自我认知清晰程度有关"},
        {"id": "S3", "name": "S3 核心价值", "desc": "与长期价值观和人生方向有关"},
        {"id": "E1", "name": "E1 依恋安全感", "desc": "与关系中的安全感和信任有关"},
        {"id": "E2", "name": "E2 情感投入度", "desc": "与情感表达和投入强度有关"},
        {"id": "E3", "name": "E3 边界与依赖", "desc": "与关系边界和依赖模式有关"},
        {"id": "A1", "name": "A1 世界观倾向", "desc": "与对世界与他人的基本判断有关"},
        {"id": "A2", "name": "A2 规则与灵活度", "desc": "与规则偏好和灵活调整有关"},
        {"id": "A3", "name": "A3 人生意义感", "desc": "与意义感、目标感和动力有关"},
        {"id": "Ac1", "name": "Ac1 行动控制", "desc": "与冲动控制和行动稳定性有关"},
        {"id": "Ac2", "name": "Ac2 执行耐力", "desc": "与持续执行和抗干扰能力有关"},
        {"id": "Ac3", "name": "Ac3 延迟满足", "desc": "与长期收益偏好和自律有关"},
        {"id": "So1", "name": "So1 社会比较", "desc": "与社会参照和比较敏感度有关"},
        {"id": "So2", "name": "So2 身份表达", "desc": "与外显身份和标签表达有关"},
        {"id": "So3", "name": "So3 群体关系", "desc": "与群体协作、归属与规范互动有关"},
    ]

    dim_defs = []
    for d in base_defs:
        qs = qmap.get(d["id"], [])
        if qs:
            qtxt = "<br/>".join([f"{x['id']}: {x['text']}" for x in qs])
        else:
            qtxt = "未抓取到题目，请重新运行生成脚本"
        dim_defs.append({
            "id": d["id"],
            "name": d["name"],
            "desc": d["desc"],
            "q": qtxt,
        })

    total_combos = int(summary.get("total_answer_combinations", 0))
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    html = """<!doctype html>
<html lang=\"zh-CN\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>SBTI 人格图鉴</title>
  <script src=\"https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js\"></script>
  <style>
    :root{--bg:#070b16;--panel:#10172b;--line:rgba(255,255,255,.13);--text:#ecf1ff;--muted:#9fadc9;--brand:#7f9bff;--brand2:#39d6aa;--warn:#f4a259;}
    *{box-sizing:border-box} body{margin:0;color:var(--text);font-family:Inter,-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;
      background:radial-gradient(1000px 600px at 80% -20%,rgba(127,155,255,.28),transparent),radial-gradient(800px 500px at -10% 10%,rgba(57,214,170,.18),transparent),var(--bg)}
    .wrap{max-width:1280px;margin:0 auto;padding:24px 16px 42px}
    .hero{padding:24px;border:1px solid var(--line);border-radius:16px;background:linear-gradient(130deg,rgba(127,155,255,.2),rgba(57,214,170,.08));}
    h1{margin:0 0 6px;font-size:34px} .muted{color:var(--muted)}
    .kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:14px 0}
    .k{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:12px} .k .l{font-size:12px;color:var(--muted)} .k .v{font-weight:700;font-size:21px;margin-top:4px}
    .sec{margin-top:14px;border:1px solid var(--line);border-radius:14px;background:var(--panel);padding:14px}
    .sec h2{margin:0 0 10px}
    .chart{height:420px}
    .toolbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:10px}
    input,select{background:#0a1020;border:1px solid var(--line);color:var(--text);padding:8px 10px;border-radius:10px}
    input{min-width:260px}
    .small{font-size:13px;color:var(--muted)}
    .map-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
    .info-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
    .info-card{border:1px solid var(--line);border-radius:10px;padding:10px;background:#0c1325}
    .dict{width:100%;border-collapse:collapse;font-size:13px}
    .dict th,.dict td{border-bottom:1px solid var(--line);padding:8px;text-align:left;vertical-align:top}
    .dict th{color:#b9c7e6;font-weight:600}
    .cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px}
    .card{background:#0c1325;border:1px solid var(--line);border-radius:12px;overflow:hidden;cursor:pointer;transition:.2s transform,.2s box-shadow}
    .card:hover{transform:translateY(-3px);box-shadow:0 10px 22px rgba(0,0,0,.35)}
    .avatar{height:180px;background:linear-gradient(135deg,#1a2546,#131b35);display:flex;align-items:center;justify-content:center}
    .avatar img{max-width:100%;max-height:100%;object-fit:contain}
    .fallback{font-size:42px;opacity:.5}
    .body2{padding:10px 12px}
    .t{font-weight:700;font-size:16px} .s{font-size:13px;color:var(--muted);margin-top:3px}
    .tag{display:inline-block;margin-top:8px;padding:3px 8px;border-radius:999px;background:rgba(127,155,255,.18);border:1px solid rgba(127,155,255,.4);font-size:12px}
    .sim-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:8px}
    .sim-item{border:1px solid var(--line);border-radius:8px;padding:6px;text-align:center;background:#0b1223}
    .sim-item b{display:block;font-size:12px;color:#b9c7e6}
    .sim-item button{margin-top:4px}
    .btn{background:#1b2a56;border:1px solid #3a4d8f;color:#e7eeff;border-radius:8px;padding:4px 8px;cursor:pointer}
    .pill{display:inline-block;border:1px solid var(--line);border-radius:999px;padding:4px 10px;font-size:12px;color:#cfe0ff;background:#0c1325}
    @media(max-width:980px){.kpis{grid-template-columns:repeat(2,1fr)} .map-grid{grid-template-columns:1fr} .info-grid{grid-template-columns:1fr} .sim-grid{grid-template-columns:repeat(3,1fr)} h1{font-size:28px}}
    @media(max-width:560px){.kpis{grid-template-columns:1fr} .chart{height:340px} .sim-grid{grid-template-columns:repeat(2,1fr)}}
  </style>
</head>
<body>
<div class=\"wrap\">
  <section class=\"hero\">
    <h1>SBTI 算法映射可视化</h1>
    <div class=\"muted\">从作答到人格命中的完整解释路径（用于理解算法，不作为心理诊断）。</div>
  </section>

  <section class=\"kpis\">
    <div class=\"k\"><div class=\"l\">人格类型数</div><div class=\"v\">__NORMAL_COUNT__</div></div>
    <div class=\"k\"><div class=\"l\">理论作答组合</div><div class=\"v\">__TOTAL_COMBOS__</div></div>
    <div class=\"k\"><div class=\"l\">形象卡片数量</div><div class=\"v\">__IMAGE_COUNT__</div></div>
    <div class=\"k\"><div class=\"l\">生成时间</div><div class=\"v\" style=\"font-size:16px\">__GENERATED_AT__</div></div>
  </section>

  <section class=\"sec\">
    <h2>为什么不同人格比例不一样？</h2>
    <div class=\"info-grid\">
      <div class=\"info-card\"><b>① 组合空间</b><div class=\"small\">默认假设所有理论作答组合等概率进入映射。</div></div>
      <div class=\"info-card\"><b>② 15维分档 + 距离匹配</b><div class=\"small\">每个组合会映射成15维向量，再与人格模板比距离。</div></div>
      <div class=\"info-card\"><b>③ 承接组合数不同</b><div class=\"small\">某些人格覆盖的组合更多，因此最终比例更高。</div></div>
    </div>
    <div id=\"flow\" class=\"chart\" style=\"height:340px;margin-top:8px\"></div>
    <div id=\"c1\" class=\"chart\"></div>
  </section>

  <section class=\"sec\">
    <h2>15维词典（每维都可解释）</h2>
    <table class=\"dict\" id=\"dimTable\"></table>
  </section>

  <section class=\"sec\">
    <h2>算法映射可视化（P0）</h2>
    <div class=\"toolbar\">
      <select id=\"uType\"></select>
      <span class=\"small\">vs</span>
      <select id=\"tType\"></select>
      <span id=\"calc\" class=\"small\"></span>
      <span id=\"judge\" class=\"pill\"></span>
    </div>
    <div class=\"map-grid\">
      <div id=\"radar\" class=\"chart\" style=\"height:360px\"></div>
      <div id=\"diff\" class=\"chart\" style=\"height:360px\"></div>
    </div>
    <div id=\"verdict\" class=\"small\" style=\"margin-top:6px\"></div>
  </section>

  <section class=\"sec\">
    <h2>边界解释（P1：Top1 vs Top2）</h2>
    <div id=\"boundary\" class=\"small\"></div>
    <div id=\"bchart\" class=\"chart\" style=\"height:300px\"></div>
  </section>

  <section class=\"sec\">
    <h2>敏感度模拟（P2：What-if）</h2>
    <div class=\"small\">点击某维的 + / - 调整 1 档，观察命中人格是否变化。</div>
    <div id=\"simGrid\" class=\"sim-grid\" style=\"margin-top:10px\"></div>
    <div id=\"simResult\" class=\"small\" style=\"margin-top:8px\"></div>
  </section>

  <section class=\"sec\">
    <h2>全部人格</h2>
    <div class=\"toolbar\">
      <input id=\"q\" placeholder=\"搜索人格：输入缩写或中文名，如 CTRL / 拿捏者\" />
      <select id=\"sort\">
        <option value=\"desc\">按占比从高到低</option>
        <option value=\"asc\">按占比从低到高</option>
      </select>
    </div>
    <div id=\"cards\" class=\"cards\"></div>
  </section>
</div>

<script>
const fullData = __FULL_DATA__;
const cardsData = __CARDS_DATA__;
const patternData = __PATTERN_DATA__;
const dimDefs = __DIM_DEFS__;
const totalCombos = __TOTAL_COMBOS_JS__;
const dimOrder = ['S1','S2','S3','E1','E2','E3','A1','A2','A3','Ac1','Ac2','Ac3','So1','So2','So3'];

function __start(){
if(typeof window.echarts==='undefined'){ setTimeout(__start,120); return; }

function bar(id,data,key,title,color){
 const c=echarts.init(document.getElementById(id));
 c.setOption({
  title:{text:title,left:'center',textStyle:{color:'#dce6ff',fontSize:14}},
  tooltip:{trigger:'axis',axisPointer:{type:'shadow'}},
  grid:{left:40,right:12,top:46,bottom:120},
  xAxis:{type:'category',data:data.map(x=>x.label),axisLabel:{color:'#a7b5d6',rotate:45,interval:0,fontSize:11},axisLine:{lineStyle:{color:'rgba(255,255,255,.2)'}}},
  yAxis:{type:'value',name:'%',nameTextStyle:{color:'#a7b5d6'},axisLabel:{color:'#a7b5d6'},splitLine:{lineStyle:{color:'rgba(255,255,255,.12)'}}},
  series:[{type:'bar',data:data.map(x=>Number(x[key]).toFixed(4)),itemStyle:{color,borderRadius:[5,5,0,0]}}]
 });
 window.addEventListener('resize',()=>c.resize());
}
bar('c1', fullData, 'percentage', '人格占比分布（含隐藏分支）', '#7f9bff');

// flow chart (P0)
const flow = echarts.init(document.getElementById('flow'));
const top = [...fullData].sort((a,b)=>b.percentage-a.percentage);
const topNodes = top.slice(0,8);
const otherPct = top.slice(8).reduce((s,x)=>s+x.percentage,0);
const links = [{source:'总组合空间', target:'进入15维映射', value:100}];
const nodes = [{name:'总组合空间'},{name:'进入15维映射'}];
for (const x of topNodes){ nodes.push({name:x.type}); links.push({source:'进入15维映射', target:x.type, value:+x.percentage.toFixed(4)}); }
nodes.push({name:'其他人格'}); links.push({source:'进入15维映射', target:'其他人格', value:+otherPct.toFixed(4)});
flow.setOption({
  title:{text:'组合流向示意（比例%）',left:'center',textStyle:{color:'#dce6ff',fontSize:14}},
  tooltip:{trigger:'item',formatter:(p)=>{
    if(typeof p.value==='number'){
      const n = Math.round(totalCombos * p.value / 100);
      return `${p.data?.source||''}${p.data?.source?' → ':''}${p.name||p.data?.target||''}<br/>占比: ${p.value.toFixed(4)}%<br/>约组合数: ${n.toLocaleString()}`;
    }
    return p.name;
  }},
  series:[{type:'sankey',data:nodes,links:links,emphasis:{focus:'adjacency'},lineStyle:{color:'source',curveness:0.5},label:{color:'#dce6ff'}}]
});
window.addEventListener('resize',()=>flow.resize());

// dim dictionary
const dimTable = document.getElementById('dimTable');
dimTable.innerHTML = '<tr><th>维度</th><th>含义</th><th>分数/分档</th><th>题目映射</th></tr>' + dimDefs.map(d=>
  `<tr><td><b>${d.id}</b><div class='small'>${d.name}</div></td><td>${d.desc}</td><td>范围 2~6；L=2-3 / M=4 / H=5-6</td><td>${d.q}</td></tr>`
).join('');

const uSel = document.getElementById('uType');
const tSel = document.getElementById('tType');
for (const p of patternData) {
  const txt = `${p.code}（${p.cn||'未命名'}）`;
  uSel.add(new Option('模拟用户：'+txt, p.code));
  tSel.add(new Option('对比模板：'+txt, p.code));
}
uSel.value = (patternData.find(x=>x.code==='OJBK')? 'OJBK' : patternData[0]?.code);
tSel.value = (patternData.find(x=>x.code==='CTRL')? 'CTRL' : patternData[1]?.code || patternData[0]?.code);

const radar = echarts.init(document.getElementById('radar'));
const diff = echarts.init(document.getElementById('diff'));
const bchart = echarts.init(document.getElementById('bchart'));

function simFromDistance(d) { return Math.max(0, Math.round((1 - d/30) * 100)); }
function nearest(vec){
  const arr = patternData.map(p=>({code:p.code,cn:p.cn,dist:p.vec.reduce((s,v,i)=>s+Math.abs(v-vec[i]),0), vec:p.vec})).sort((a,b)=>a.dist-b.dist);
  return arr;
}

let simOffsets = Array(15).fill(0);

function updateAll() {
  const u = patternData.find(x=>x.code===uSel.value);
  const t = patternData.find(x=>x.code===tSel.value);
  if(!u||!t) return;

  const d = u.vec.map((v,i)=>Math.abs(v-t.vec[i]));
  const distance = d.reduce((a,b)=>a+b,0);
  const exact = d.filter(x=>x===0).length;
  const similarity = simFromDistance(distance);
  document.getElementById('calc').textContent = `distance=${distance} · exact=${exact}/15 · similarity=${similarity}%`;

  const topGap = d.map((x,i)=>({dim:dimOrder[i],v:x})).sort((a,b)=>b.v-a.v).slice(0,3).filter(x=>x.v>0);
  document.getElementById('verdict').textContent = topGap.length
    ? `判定解释：当前对比差异主要由 ${topGap.map(x=>x.dim).join(' / ')} 拉开。`
    : '判定解释：两者完全一致（distance=0）。';

  radar.setOption({
    title:{text:'15维向量对比',left:'center',textStyle:{color:'#dce6ff',fontSize:14}},
    tooltip:{},
    legend:{top:28,textStyle:{color:'#b9c7e6'},data:[`${u.code}`,`${t.code}`]},
    radar:{center:['50%','58%'], radius:120, indicator: dimOrder.map(x=>({name:x,max:3})), axisName:{color:'#a7b5d6'}, splitLine:{lineStyle:{color:'rgba(255,255,255,.14)'}}, splitArea:{areaStyle:{color:['rgba(255,255,255,.02)','rgba(255,255,255,.01)']}}, axisLine:{lineStyle:{color:'rgba(255,255,255,.2)'}}},
    series:[{type:'radar',data:[{value:u.vec,name:u.code,areaStyle:{color:'rgba(127,155,255,.25)'},lineStyle:{color:'#7f9bff'}},{value:t.vec,name:t.code,areaStyle:{color:'rgba(57,214,170,.22)'},lineStyle:{color:'#39d6aa'}}]}]
  });

  diff.setOption({
    title:{text:'逐维差值 |u_i - t_i|',left:'center',textStyle:{color:'#dce6ff',fontSize:14}},
    tooltip:{trigger:'axis',axisPointer:{type:'shadow'}},
    grid:{left:40,right:12,top:46,bottom:90},
    xAxis:{type:'category',data:dimOrder,axisLabel:{color:'#a7b5d6'},axisLine:{lineStyle:{color:'rgba(255,255,255,.2)'}}},
    yAxis:{type:'value',min:0,max:2,axisLabel:{color:'#a7b5d6'},splitLine:{lineStyle:{color:'rgba(255,255,255,.12)'}}},
    visualMap:{show:false,min:0,max:2,inRange:{color:['#39d6aa','#f4a259','#ff6b6b']}},
    series:[{type:'bar',data:d,itemStyle:{borderRadius:[5,5,0,0]}}]
  });

  // P1 boundary top1 vs top2
  const rank = nearest(u.vec);
  const top1 = rank[0], top2 = rank[1];
  const bdiff = top1.vec.map((v,i)=>Math.abs(v-top2.vec[i]));
  const decisive = bdiff.map((v,i)=>({dim:dimOrder[i],v})).sort((a,b)=>b.v-a.v).slice(0,5);
  document.getElementById('boundary').textContent = `Top1：${top1.code}（distance=${top1.dist}） vs Top2：${top2.code}（distance=${top2.dist}）。边界维度：${decisive.filter(x=>x.v>0).map(x=>x.dim).join(' / ') || '差异很小'}。`;
  bchart.setOption({
    title:{text:'Top1 与 Top2 的模板差异维度',left:'center',textStyle:{color:'#dce6ff',fontSize:14}},
    tooltip:{trigger:'axis',axisPointer:{type:'shadow'}},
    grid:{left:40,right:12,top:46,bottom:70},
    xAxis:{type:'category',data:dimOrder,axisLabel:{color:'#a7b5d6'}},
    yAxis:{type:'value',min:0,max:2,axisLabel:{color:'#a7b5d6'},splitLine:{lineStyle:{color:'rgba(255,255,255,.12)'}}},
    series:[{type:'bar',data:bdiff,itemStyle:{color:'#9ab3ff',borderRadius:[4,4,0,0]}}]
  });

  // P2 sensitivity
  const simGrid = document.getElementById('simGrid');
  simGrid.innerHTML = dimOrder.map((dname,idx)=>`
    <div class='sim-item'>
      <b>${dname}</b>
      <div>偏移: ${simOffsets[idx]}</div>
      <button class='btn' onclick='adj(${idx},-1)'>-</button>
      <button class='btn' onclick='adj(${idx},1)'>+</button>
    </div>`).join('');
  const vec2 = u.vec.map((v,i)=>Math.max(1,Math.min(3,v+simOffsets[i])));
  const after = nearest(vec2);
  const beforeTop = rank[0];
  const afterTop = after[0];
  const changed = beforeTop.code !== afterTop.code;
  document.getElementById('simResult').textContent = changed
    ? `模拟结果：命中从 ${beforeTop.code} 变为 ${afterTop.code}（distance ${beforeTop.dist} -> ${afterTop.dist}）。`
    : `模拟结果：仍命中 ${afterTop.code}（distance=${afterTop.dist}，similarity≈${simFromDistance(afterTop.dist)}%）。`;
  document.getElementById('judge').textContent = `当前最近人格：${beforeTop.code}（相似度≈${simFromDistance(beforeTop.dist)}%）`;
}

window.adj = function(i,delta){
  simOffsets[i] = Math.max(-1, Math.min(1, simOffsets[i] + delta));
  updateAll();
}

uSel.addEventListener('change',()=>{ simOffsets=Array(15).fill(0); updateAll(); });
tSel.addEventListener('change',updateAll);
updateAll();
window.addEventListener('resize',()=>{radar.resize(); diff.resize(); bchart.resize();});

// cards
const cardsEl=document.getElementById('cards');
function avatarHtml(x){
  return x.image
    ? `<img src=\"${x.image}\" alt=\"${x.code}\"/>`
    : `<div class=\"fallback\">◉</div>`;
}
function renderCards(){
 const q=(document.getElementById('q').value||'').trim().toLowerCase();
 const sort=document.getElementById('sort').value;
 let arr=[...cardsData].filter(x=>`${x.code} ${x.cn}`.toLowerCase().includes(q));
 arr.sort((a,b)=>sort==='desc'?b.share-a.share:a.share-b.share);
 cardsEl.innerHTML=arr.map(x=>`<div class=\"card\"><div class=\"avatar\">${avatarHtml(x)}</div><div class=\"body2\"><div class=\"t\">${x.code}（${x.cn||'未命名'}）</div><div class=\"s\">理论占比：${x.share.toFixed(4)}%</div></div></div>`).join('');
}
document.getElementById('q').addEventListener('input',renderCards);
document.getElementById('sort').addEventListener('change',renderCards);
renderCards();
}
__start();
</script>
</body></html>
"""

    html = (
        html.replace("__NORMAL_COUNT__", str(summary.get("normal_type_count", "-")))
        .replace("__TOTAL_COMBOS__", str(total_combos))
        .replace("__IMAGE_COUNT__", str(summary.get("image_count", 0)))
        .replace("__GENERATED_AT__", generated_at)
        .replace("__FULL_DATA__", json.dumps(full[["type", "cn", "label", "percentage"]].to_dict(orient="records"), ensure_ascii=False))
        .replace("__CARDS_DATA__", json.dumps(cards, ensure_ascii=False))
        .replace("__PATTERN_DATA__", json.dumps(pattern_rows, ensure_ascii=False))
        .replace("__DIM_DEFS__", json.dumps(dim_defs, ensure_ascii=False))
        .replace("__TOTAL_COMBOS_JS__", str(total_combos))
    )

    DOCS.mkdir(parents=True, exist_ok=True)
    out = DOCS / "index.html"
    out.write_text(html, encoding="utf-8")
    print(f"Generated: {out}")


if __name__ == "__main__":
    main()
