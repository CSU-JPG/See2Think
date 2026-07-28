"""Build a standalone, shareable annotation package for the 180 YZR cases."""

from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "yzrcheck"
OUTPUT = ROOT / "deliverables" / "See2Think_HumanValidation180_Annotation_20260719"

INDEX = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>See2Think Human Validation (180)</title><link rel="stylesheet" href="styles.css"></head>
<body><header><div><h1>See2Think Human Validation</h1><p>180 trajectories · judge-decision quality annotation</p></div><div id="progress"></div></header>
<main><aside><label>Model<select id="model"></select></label><label>Task group<select id="group"></select></label><label>Stratum<select id="stratum"></select></label><div id="list"></div></aside>
<section id="content"><div class="empty">Loading cases…</div></section></main><script src="app.js"></script></body></html>\n"""

CSS = """*{box-sizing:border-box}body{margin:0;background:#101418;color:#e8eaed;font:15px/1.45 system-ui,Segoe UI,Arial,sans-serif}header{padding:18px 28px;border-bottom:1px solid #30363d;display:flex;justify-content:space-between;align-items:center;background:#171b21}h1{font-size:22px;margin:0}header p{margin:4px 0 0;color:#aab2bd}main{display:grid;grid-template-columns:270px 1fr;min-height:calc(100vh - 82px)}aside{padding:16px;border-right:1px solid #30363d;position:sticky;top:0;height:calc(100vh - 82px);overflow:auto}label{display:block;margin-bottom:12px;color:#cbd2da;font-weight:600}select,button,textarea{font:inherit}select,textarea{width:100%;margin-top:5px;background:#20262e;color:#e8eaed;border:1px solid #47515c;border-radius:6px;padding:8px}.case{width:100%;text-align:left;border:0;border-bottom:1px solid #2c333c;background:transparent;color:#d5dbe3;padding:9px;cursor:pointer}.case.active{background:#24415c}.case.done:after{content:' ✓';color:#75d48b}.case small{display:block;color:#9eabb8}#content{padding:24px;max-width:1500px}.top{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}.badge{display:inline-block;padding:3px 8px;border-radius:999px;background:#2b3540;margin:0 5px 5px 0;font-size:12px}.card{background:#171c22;border:1px solid #303943;border-radius:9px;padding:16px;margin:14px 0}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.metric{padding:12px;background:#1d242c;border-radius:7px}.metric strong{display:block}.reason{color:#b8c1cb;font-size:13px;margin:6px 0 0}.images{display:flex;flex-wrap:wrap;gap:10px}.images img{max-width:31%;max-height:330px;border:1px solid #414b56;background:#fff;object-fit:contain}.choice{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px}.choice label{font-weight:400;background:#242c35;padding:7px 9px;border-radius:6px;margin:0;cursor:pointer}.choice input{accent-color:#62b5ff}.nav button,.export button{background:#2f81c8;color:#fff;border:0;border-radius:6px;padding:8px 12px;cursor:pointer;margin-left:7px}.export button{background:#365a42}.text{white-space:pre-wrap;max-height:420px;overflow:auto;background:#0f1317;padding:12px;border-radius:6px;color:#d7dde5}.empty{padding:32px;color:#aab2bd}@media(max-width:850px){main{grid-template-columns:1fr}aside{height:auto;position:static;border-right:0;border-bottom:1px solid #30363d}.grid{grid-template-columns:1fr}.images img{max-width:100%}}\n"""

APP = r"""const FIELDS=[['key_step_selection','Key-step selection','Whether the selected key visual step is reasonable.'],['action_relevance','Action relevance','Whether the judge decision on action relevance is reasonable.'],['render_faithfulness','Render faithfulness','Whether the judge decision on render faithfulness is reasonable.'],['feedback_uptake','Feedback uptake','Whether the judge decision on feedback uptake is reasonable.']];
const VALUES=[['reasonable','Reasonable'],['partial','Partially reasonable'],['unreasonable','Unreasonable']]; const KEY='see2think_human_validation_180_standalone_v1';
let rows=[],current=0,annotations=JSON.parse(localStorage.getItem(KEY)||'{}'); const $=s=>document.querySelector(s);
const esc=s=>String(s??'').replace(/[&<>"']/g,x=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[x]));
function parse(t){let [h,...a]=t.trim().split(/\r?\n/);let keys=h.split(',');return a.map(l=>{let p=l.split(',');return Object.fromEntries(keys.map((k,i)=>[k,p[i]??'']))})}
function done(r){let a=annotations[r.case_index]||{};return FIELDS.every(([k])=>a[k])}
function filtered(){let m=$('#model').value,g=$('#group').value,s=$('#stratum').value;return rows.filter(r=>(!m||r.model===m)&&(!g||r.task_group===g)&&(!s||r.stratum===s))}
function options(id,field){let vals=[...new Set(rows.map(r=>r[field]))].sort();$(id).innerHTML='<option value="">All</option>'+vals.map(v=>`<option>${esc(v)}</option>`).join('')}
function refreshList(){let f=filtered(),box=$('#list');box.innerHTML=f.map(r=>`<button class="case ${rows[current]?.case_index===r.case_index?'active':''} ${done(r)?'done':''}" data-i="${rows.indexOf(r)}">#${r.case_index} · ${esc(r.model)}<small>${esc(r.task_group)} · ${esc(r.stratum)}<br>${esc(r.task_key)}</small></button>`).join('');box.querySelectorAll('button').forEach(b=>b.onclick=()=>{current=+b.dataset.i;render()})}
async function loadText(url){let r=await fetch(url);return r.ok?r.text():''} async function loadJSON(url){let r=await fetch(url);return r.ok?r.json():{}}
function store(){localStorage.setItem(KEY,JSON.stringify(annotations));$('#progress').textContent=`Completed: ${rows.filter(done).length} / 180`;refreshList()}
async function render(){let r=rows[current],dir='cases/'+r.case_dir;$('#content').innerHTML='<div class="empty">Loading case…</div>';let [meta,q,steps]=await Promise.all([loadJSON(dir+'/metadata.json'),loadText(dir+'/q.md'),loadText(dir+'/steps.md')]);let a=annotations[r.case_index]||{};let metrics=FIELDS.map(([key,label,help])=>`<div class="metric"><strong>${esc(label)}</strong><span class="badge">Judge score: ${esc(meta[key]??'n/a')}</span><p class="reason">${esc(meta[key+'_reason']||help)}</p><div class="choice">${VALUES.map(([v,l])=>`<label><input type="radio" name="${key}" value="${v}" ${a[key]===v?'checked':''}> ${l}</label>`).join('')}</div></div>`).join('');let imgs=(meta.copied_images||[]).map(n=>`<a href="${dir}/${encodeURIComponent(n)}" target="_blank"><img src="${dir}/${encodeURIComponent(n)}" alt="${esc(n)}"></a>`).join('');$('#content').innerHTML=`<div class="top"><div><h2>Case #${r.case_index}: ${esc(r.task_key)}</h2><span class="badge">${esc(r.model)}</span><span class="badge">${esc(r.task_group)}</span><span class="badge">${esc(r.stratum)}</span><span class="badge">stratum match: ${esc(r.stratum_match)}</span></div><div class="nav"><button id="prev">← Previous</button><button id="next">Next →</button></div></div><div class="card"><b>Key-step selected by judge:</b> ${esc(meta.key_step_id??'n/a')}<p class="reason">${esc(meta.key_step_reason||'')}</p></div><div class="card"><h3>Images</h3><div class="images">${imgs||'<i>No copied images.</i>'}</div></div><div class="card"><h3>Judge decisions — annotate each one</h3><div class="grid">${metrics}</div><label>Optional note<textarea id="note" rows="3">${esc(a.note||'')}</textarea></label></div><div class="card"><h3>Question</h3><div class="text">${esc(q)}</div><h3>Trajectory</h3><div class="text">${esc(steps)}</div></div><div class="export"><button id="json">Export JSON</button><button id="csv">Export CSV</button></div>`;
 $('#content').querySelectorAll('input[type=radio]').forEach(x=>x.onchange=()=>{annotations[r.case_index]={...a,[x.name]:x.value,note:$('#note').value,case_index:+r.case_index,task_key:r.task_key,model:r.model,task_group:r.task_group,stratum:r.stratum,updated_at:new Date().toISOString()};store()});$('#note').onchange=()=>{annotations[r.case_index]={...a,note:$('#note').value,case_index:+r.case_index,task_key:r.task_key,model:r.model,task_group:r.task_group,stratum:r.stratum,updated_at:new Date().toISOString()};store()};$('#prev').onclick=()=>{current=(current-1+rows.length)%rows.length;render()};$('#next').onclick=()=>{current=(current+1)%rows.length;render()};$('#json').onclick=()=>download('see2think_human_annotations_180.json',JSON.stringify({exported_at:new Date().toISOString(),count:Object.keys(annotations).length,annotations:Object.values(annotations)},null,2),'application/json');$('#csv').onclick=()=>{let h=['case_index','task_key','model','task_group','stratum',...FIELDS.map(x=>x[0]),'note','updated_at'];let csv=[h.join(','),...Object.values(annotations).map(o=>h.map(k=>'"'+String(o[k]??'').replaceAll('"','""')+'"').join(','))].join('\n');download('see2think_human_annotations_180.csv',csv,'text/csv')};}
function download(name,text,type){let a=document.createElement('a');a.href=URL.createObjectURL(new Blob([text],{type}));a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),500)}
fetch('cases/index.csv').then(r=>r.text()).then(t=>{rows=parse(t);options('#model','model');options('#group','task_group');options('#stratum','stratum');['#model','#group','#stratum'].forEach(x=>$(x).onchange=refreshList);store();refreshList();render()}).catch(e=>$('#content').innerHTML='<div class="empty">Could not load data. Start the local server using START_ANNOTATION.bat, then visit http://127.0.0.1:8765.</div>');
"""

README = """# See2Think Human Validation (180 cases)

This package contains a standalone annotation interface and the 180 sampled VAoT-Full trajectories used for human validation. It contains no complete 1,200-task benchmark or unrelated experiment outputs.

## Start

1. Extract the ZIP completely to a local folder. Do not open the HTML file directly.
2. Double-click `START_ANNOTATION.bat`.
3. Your browser should open `http://127.0.0.1:8767/index.html`. If it does not, paste that address into a browser.
4. Keep the command window open while annotating. Close it only after exporting your results.

Python 3 must be available in the system PATH. If the script reports that Python is unavailable, install Python 3 or run `python -m http.server 8765` in this folder and then open the address above.

## What to annotate

Each of the 180 cases contains four LLM-judge decisions. For each decision, select exactly one label:

- **Reasonable**: the judge decision is clearly justified by the trajectory and images.
- **Partially reasonable**: broadly plausible, but incomplete, ambiguous, or partly inaccurate.
- **Unreasonable**: contradicted by the trajectory/images or not supported by the evidence.

The four targets are: key-step selection, action relevance, render faithfulness, and feedback uptake. Use the displayed judge explanation, question, trajectory, and rendered images to make the decision.

## Saving and submission

Selections are saved automatically in the browser on the current computer. Before closing the browser, use **Export JSON** or **Export CSV** at the bottom of any case and send the downloaded file back to the project owner. The package itself does not upload any annotations.

## Sampling

The 180 cases are stratified as: 3 models × 3 task groups (2D/3D/Real) × 4 strata × 5 cases. A `stratum_match=false` badge identifies a documented supplement for a cell with too few strict candidates.
"""

BAT = r"""@echo off
cd /d "%~dp0"
start "" /b python -m http.server 8767
timeout /t 2 /nobreak >nul
start "See2Think annotation" http://127.0.0.1:8767/index.html
echo Annotation server is running at http://127.0.0.1:8767/index.html
pause
"""


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    cases = OUTPUT / "cases"
    cases.mkdir(exist_ok=True)
    shutil.copy2(SOURCE / "index.csv", cases / "index.csv")
    for case in sorted(SOURCE.iterdir()):
        if case.is_dir() and case.name[:3].isdigit():
            destination = cases / case.name
            if not destination.exists():
                shutil.copytree(case, destination)
    (OUTPUT / "index.html").write_text(INDEX, encoding="utf-8")
    (OUTPUT / "styles.css").write_text(CSS, encoding="utf-8")
    (OUTPUT / "app.js").write_text(APP, encoding="utf-8")
    (OUTPUT / "README.md").write_text(README, encoding="utf-8")
    (OUTPUT / "START_ANNOTATION.bat").write_text(BAT, encoding="utf-8")
    archive = shutil.make_archive(str(OUTPUT), "zip", root_dir=OUTPUT)
    print(f"package={OUTPUT}")
    print(f"zip={archive}")


if __name__ == "__main__":
    main()
