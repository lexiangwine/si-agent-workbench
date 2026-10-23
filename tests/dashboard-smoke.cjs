// DOM interaction test without a browser dependency; does not validate layout.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
class Element {
  constructor(tag='div') { this.tagName=tag; this.children=[]; this.textContent=''; this.hidden=false; }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children=[...children]; }
  scrollIntoView() { this.scrolled=true; }
}
const elements = new Map();
const document = {getElementById(id) { if(!elements.has(id))elements.set(id,new Element());return elements.get(id); },createElement(tag) {return new Element(tag);}};
let fail=false, empty=false;
const sample={name:'p001',workflow:'delivery',mode:'production',status:'in_progress',stages:[{id:'requirements',title:'需求确认',role:'analyst',gate:'G1',status:'pending_review',source:'manual'}]};
const context=vm.createContext({document,Date,encodeURIComponent,fetch:async url=>{
  if(fail) return {ok:false,json:async()=>({error:'模拟断连'})};
  if(url.startsWith('/api/artifact')) return {ok:true,json:async()=>({text:'<script>example</script> 仅文本预览'})};
  return {ok:true,json:async()=>({projects:empty?[]:[sample]})};
}});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../workbench/dashboard.js'),'utf8'),context);
const tick=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
  await tick();
  assert.equal(document.getElementById('count').textContent,1);
  assert.equal(document.getElementById('pending').textContent,1);
  assert.equal(document.getElementById('project-list').children.length,1);
  const detail=document.getElementById('detail');
  const row=detail.children.find(x=>x.className==='stage');
  const preview=row.children[2].children[1];
  await preview.onclick();
  assert.equal(document.getElementById('artifact').hidden,false);
  assert.match(document.getElementById('artifact-text').textContent,/^<script>/);
  assert.equal(document.getElementById('artifact-text').children.length,0);
  document.getElementById('close-artifact').onclick();
  assert.equal(document.getElementById('artifact').hidden,true);
  fail=true;await document.getElementById('refresh').onclick();
  assert.equal(document.getElementById('error').textContent,'模拟断连');
  assert.equal(document.getElementById('refresh').disabled,false);
  fail=false;empty=true;await document.getElementById('refresh').onclick();
  assert.equal(document.getElementById('count').textContent,0);
  assert.equal(document.getElementById('project-list').children.length,0);
  assert.equal(document.getElementById('detail').children[0].textContent,'工作区已就绪');
  console.log('PASS: dashboard interaction (load, preview as text, close, error, refresh, empty state)');
})().catch(e=>{console.error(e);process.exitCode=1;});
