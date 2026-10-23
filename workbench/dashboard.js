"use strict";
const $ = id => document.getElementById(id);
const labels = {not_started:"未开始",pending_review:"待审核",approved:"已审批",demo_approved:"模拟审批",stale:"版本已变化",complete:"已完成",demo_complete:"演示完成",in_progress:"进行中",invalid:"记录异常"};
let projects = [], selected = null;
function el(tag, text, cls) { const n = document.createElement(tag); if(text !== undefined) n.textContent = text; if(cls) n.className = cls; return n; }
async function api(url) { const r = await fetch(url, {cache:"no-store"}); const data = await r.json(); if(!r.ok) throw new Error(data.error || "读取失败"); return data; }
function showError(e) { $("error").hidden = false; $("error").textContent = e.message; }
function render() {
  $("count").textContent = projects.length;
  $("production").textContent = projects.filter(p=>p.mode==="production").length;
  $("pending").textContent = projects.flatMap(p=>p.stages).filter(s=>s.status==="pending_review").length;
  $("stale").textContent = projects.flatMap(p=>p.stages).filter(s=>s.status==="stale").length;
  const list = $("project-list"); list.replaceChildren();
  for(const p of projects) { const b = el("button", undefined, "project"+(p.name===selected?" selected":"")); b.append(el("b",p.name),el("small",(p.workflow||"未知流程")+" · "+(labels[p.status]||p.status))); b.onclick=()=>{selected=p.name;$("artifact").hidden=true;render();}; list.append(b); }
  const detail = $("detail"); detail.replaceChildren(); const p = projects.find(x=>x.name===selected);
  if(!p) {detail.append(el("h3","工作区已就绪"),el("p","暂无项目。运行下方离线演示命令，然后刷新状态。","note")); return;}
  const header=el("div",undefined,"project-header"); header.append(el("h3",p.name),el("span",p.mode==="demo"?"离线演示":"正式项目","badge"+(p.mode==="demo"?" demo":"")));detail.append(header);
  detail.append(el("p",p.mode==="demo"?"仅验证流程，不是真实模型成果；模拟审批不等于业务验收。":"审批绑定输入与输出版本，改动后需要重新审核。","note"));
  for(const s of p.stages) { const row=el("div",undefined,"stage"), title=el("div");title.append(el("b",s.title),el("small",s.role+" / "+s.id));const actions=el("div",undefined,"stage-action");actions.append(el("span",labels[s.status]||s.status,"state "+s.status));
    if(s.source) {const b=el("button","查看交付");b.onclick=async()=>{try {const data=await api("/api/artifact?project="+encodeURIComponent(p.name)+"&stage="+encodeURIComponent(s.id));$("artifact-title").textContent=s.title;$("artifact-text").textContent=data.text;$("artifact").hidden=false;$("artifact").scrollIntoView({behavior:"smooth",block:"start"});}catch(e){showError(e);}};actions.append(b);}
    row.append(el("span",s.gate,"gate"),title,actions);detail.append(row);
  }
}
async function refresh() { $("refresh").disabled=true;try {const data=await api("/api/projects");projects=data.projects;if(!projects.some(p=>p.name===selected))selected=projects[0]?.name||null;$("error").hidden=true;$("updated").textContent="更新于 "+new Date().toLocaleTimeString();render();}catch(e){showError(e);}finally{$("refresh").disabled=false;} }
$("refresh").onclick=refresh;$("close-artifact").onclick=()=>{$("artifact").hidden=true;};refresh();
