/* Synthetic DOM integration only; no layout or real-browser signoff. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),{webcrypto}=require('node:crypto'),{JSDOM,VirtualConsole}=require('jsdom');
const root=path.resolve(__dirname,'..'),raw=fs.readFileSync(path.join(root,'docs/predictor/predictor-data-20261118.json'),'utf8'),data=JSON.parse(raw),old=fs.readFileSync(path.join(root,'docs/service-followup/followup-data-20261117.json'),'utf8'),html=fs.readFileSync(process.argv[2],'utf8');
let errors=[];const checks={controlStates:0,pointQuantiles:0,fullTailPairs:0,models:0,offHappyPath:0};
function make(fail=false){const vc=new VirtualConsole();vc.on('jsdomError',e=>errors.push(e.message));return new JSDOM(html,{url:'http://127.0.0.1:8765/',runScripts:'dangerously',virtualConsole:vc,beforeParse(w){Object.defineProperty(w,'crypto',{value:webcrypto});Object.assign(w,{TextEncoder,TextDecoder,Blob,Response,DecompressionStream});w.fetch=async url=>{if(fail)throw Error('Deliberate offline failure');return {ok:true,text:async()=>String(url).includes('predictor-data')?raw:old};};w.HTMLElement.prototype.scrollIntoView=function(){};w.ResizeObserver=class{observe(){}disconnect(){}unobserve(){}};}});}
const dom=make(),w=dom.window,d=w.document,$=id=>d.getElementById('pf-'+id),format=x=>x>=1e6?(x/1e6).toFixed(3)+' ms':x>=1000?(x/1000).toFixed(3)+' µs':Math.round(x)+' ns';
function select(id,value){$(id).value=value;$(id).dispatchEvent(new w.Event('change',{bubbles:true}));checks.controlStates++;}
async function settle(test){for(let i=0;i<250;i++){if(test())return;await new Promise(r=>setTimeout(r,20));}throw Error('DOM async timeout');}
async function close(dom){const s=dom.window.document.getElementById('tail-status');if(s)await settle(()=>!s.textContent.startsWith('Decoding'));dom.window.close();}
(async()=>{
 assert.equal(d.querySelector('#predictor-followup').dataset.ready,'true');assert.equal(d.querySelector('#service-followup').dataset.ready,'true');assert.equal($('cohort').value,'validation');assert.equal($('table').querySelectorAll('tbody tr').length,15);assert.equal($('all-table').querySelectorAll('tbody tr').length,30);
 for(const cohort of Object.keys(data.cohortInputs)){
  select('cohort',cohort);
  for(const stage of Array.from($('stage').options).map(x=>x.value)){
   select('stage',stage);
   for(const channel of Array.from($('metric').options).map(x=>x.value)){
    select('metric',channel);
    for(const q of ['99','99.9','99.99','99.999']){
     select('q',q);assert(!/NaN|undefined|Infinity/.test($('ratio').innerHTML));assert(!/NaN|Infinity/.test($('prediction').innerHTML));
    }
   }
  }
  for(const model of ['M1','M2','constant']){select('model',model);assert(!/NaN|undefined|Infinity/.test($('errors').innerHTML));checks.models++;}
 }
 select('model','M2');
 for(const p of data.points){
  $('all-table').querySelector(`[data-point="${p.id}"]`).click();assert.equal($('cohort').value,p.cohort);assert($('detail-title').textContent.includes(`${p.writeBps/100}% writes`));
  for(const q of ['99','99.9','99.99','99.999']){
   select('q',q);for(const id of [p.pairs[0].c,p.pairs[0].h]){const r=data.forks.find(x=>x.id===id);assert($('detail').textContent.includes(format(r.latency.response.percentilesNs[q])));checks.pointQuantiles++;}
  }
  $('load-tail').click();await settle(()=>$('tail').querySelector('svg'));assert.equal($('rates').querySelectorAll('tbody tr').length,2);assert(!/NaN|Infinity/.test($('tail').innerHTML));checks.fullTailPairs++;
 }
 assert.equal(errors.length,0,errors.join('; '));await close(dom);
 for(const mode of ['fetch','codec']){
  const bad=make(mode==='fetch');if(mode==='codec')bad.window.DecompressionStream=undefined;
  bad.window.document.getElementById('pf-load-tail').click();await settle(()=>bad.window.document.getElementById('pf-tail').textContent.includes('unavailable'));assert(bad.window.document.getElementById('pf-table').querySelector('tbody tr'));assert.equal(bad.window.document.getElementById('pf-rates').textContent,'');checks.offHappyPath++;await close(bad);
 }
 assert.equal(errors.length,0,errors.join('; '));
 const receipt={passed:true,method:'jsdom27.2.0 synthetic DOM integration',...checks,completeStagedHtml:true,oldComponentInitializes:true,browserVisualQaPerformed:false,browserVisualQaReason:'CUA browser host unavailable',limits:'No browser layout, viewport, screenshot or authenticated browser signoff. Scientific PNGs inspected separately.'};fs.writeFileSync(path.join(root,'docs/interactive/predictor-dom-qa-20261118.json'),JSON.stringify(receipt,null,2)+'\n');console.log(JSON.stringify(receipt));
})().catch(e=>{console.error(e);dom.window.close();process.exitCode=1;});
