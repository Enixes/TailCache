/* DOM-level integration checks; not a browser layout/interaction signoff.
 * Usage: NODE_PATH=/tmp/tailcache-dom-qa/node_modules node this-file <component.html>
 */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {webcrypto}=require('node:crypto');
const {JSDOM,VirtualConsole}=require('jsdom');
const root=path.resolve(__dirname,'..'),raw=fs.readFileSync(path.join(root,'docs/service-followup/followup-data-20261117.json'),'utf8');
const data=JSON.parse(raw),checks={controlStates:0,quantileDetailChecks:0,fullTailPairs:0,offHappyPath:0};
const html=fs.readFileSync(process.argv[2],'utf8');
let errors=[];
function make(failFetch=false){const vc=new VirtualConsole();vc.on('jsdomError',e=>errors.push(e.message));return new JSDOM(html,{url:'http://127.0.0.1:8765/',runScripts:'dangerously',virtualConsole:vc,beforeParse(w){
  Object.defineProperty(w,'crypto',{value:webcrypto});Object.assign(w,{TextEncoder,TextDecoder,Blob,Response,DecompressionStream});
  w.fetch=async()=>{if(failFetch)throw Error('Deliberate offline failure');return {ok:true,text:async()=>raw};};
  w.HTMLElement.prototype.scrollIntoView=function(){};
  // jsdom has no layout engine. This stub permits the older component to initialize;
  // it cannot establish responsive layout or observer-driven resize behavior.
  w.ResizeObserver=class {observe(){} unobserve(){} disconnect(){}};
}});}
const dom=make(),w=dom.window,d=w.document,$=id=>d.getElementById('sf-'+id);
function select(id,v){$(id).value=v;$(id).dispatchEvent(new w.Event('change',{bubbles:true}));checks.controlStates++;}
async function settle(test){for(let i=0;i<150;i++){if(test())return;await new Promise(r=>setTimeout(r,20));}throw Error('DOM async check timed out');}
async function close(dom){const status=dom.window.document.getElementById('tail-status');if(status)await settle(()=>!status.textContent.startsWith('Decoding'));dom.window.close();}
const format=x=>x>=1e6?(x/1e6).toFixed(3)+' ms':x>=1000?(x/1000).toFixed(3)+' µs':Math.round(x)+' ns';
(async()=>{
 assert.equal(d.querySelector('#service-followup').dataset.ready,'true');assert.equal($('cohort').value,'geometry');
 assert.equal($('table').querySelectorAll('tbody tr').length,2);assert.equal($('all-table').querySelectorAll('tbody tr').length,58);
 for(const c of Object.keys(data.cohortInputs)){
  select('cohort',c);
  const stages=Array.from($('stage').options).map(v=>v.value);
  for(const stage of stages){select('stage',stage);
   for(const channel of Array.from($('metric').options).map(v=>v.value)){select('metric',channel);
    for(const q of ['99','99.9','99.99','99.999']){select('q',q);
     const points=data.points.filter(p=>p.cohort===c&&(stage==='all'||p.stage===stage));
     assert.equal($('table').querySelectorAll('tbody tr').length,points.length);
     assert.match($('scope').textContent,new RegExp('p'+q.replaceAll('.','\\.')));
     assert(!/NaN|undefined|Infinity/.test($('ratio').innerHTML));
     for(const p of points){$ ('table').querySelector(`[data-point="${p.id}"]`).click();
      for(const pair of p.pairs){select('block',String(pair.block));
       for(const id of [pair.c,pair.h]){const f=data.forks.find(f=>f.id===id),value=f.latency[channel].percentilesNs[q];assert($('detail').textContent.includes(format(value)));checks.quantileDetailChecks++;}
      }
     }
    }
   }
  }
 }
 // All-point navigation must set the cohort, stage, primary channel and selected point together.
 $('all-table').querySelector('[data-point="cell-1"]').click();assert.equal($('cohort').value,'geometry');assert.match($('detail-title').textContent,/Repeated-short/);
 // Load both codec kinds via the actual component button; they have different count semantics.
 for(const cohort of ['geometry','observer']){select('cohort',cohort);$('load-tail').click();await settle(()=>$('tail').querySelector('svg'));assert.equal($('rates').querySelectorAll('tbody tr').length,2);assert(!/NaN|Infinity/.test($('tail').innerHTML));checks.fullTailPairs++;}
 assert.match($('detail').textContent,/retained samples/);assert.match($('tail-note').textContent,/reported JMH sample/);
 assert.equal(errors.length,0,errors.join('; '));await close(dom);
 const bad=make(true);bad.window.document.getElementById('sf-load-tail').click();await settle(()=>bad.window.document.getElementById('sf-tail').textContent.includes('unavailable'));
 assert(bad.window.document.getElementById('sf-table').querySelector('tbody tr'));checks.offHappyPath++;await close(bad);
 const missing=make();missing.window.DecompressionStream=undefined;missing.window.document.getElementById('sf-load-tail').click();await settle(()=>missing.window.document.getElementById('sf-tail').textContent.includes('unavailable'));checks.offHappyPath++;await close(missing);
 assert.equal(errors.length,0,errors.join('; '));
 const receipt={passed:true,method:'jsdom 29.0.0 DOM integration, synthetic events; not a real browser',inputMode:html.includes('id="study-data"')?'Complete staged hosted HTML':'Isolated component',resizeObserverStubbed:true,...checks,browserVisualQaPerformed:false,browserVisualQaReason:'CUA browser access host unavailable; no security settings or browser protection changed',limits:'No layout, responsive viewport or real-browser interaction signoff. Separate scientific PNG figures visually inspected.'};
 fs.writeFileSync(path.join(root,'docs/interactive/service-dom-qa-20261117.json'),JSON.stringify(receipt,null,2)+'\n');console.log(JSON.stringify(receipt));
})().catch(e=>{console.error(e);dom.window.close();process.exitCode=1;});
