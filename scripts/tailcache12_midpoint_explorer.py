#!/usr/bin/env python3
"""Build the fresh-cohort panel without changing historical explorer data."""
import hashlib,json,pathlib,re,shutil

ROOT=pathlib.Path.cwd()
DATA=ROOT/'evidence-archives/midpoint-results-20261110-001'
START='<!-- TAILCACHE_MIDPOINT_START -->'
END='<!-- TAILCACHE_MIDPOINT_END -->'

PANEL=r'''
<style>
#midpoint-followup{margin:28px 0;padding:24px;background:#fff;border:1px solid #b8c9dc;border-radius:10px;color:#172033;font:15px/1.5 system-ui,sans-serif}#midpoint-followup *{box-sizing:border-box}#midpoint-followup{overflow-wrap:anywhere}#midpoint-followup h2{font-size:24px;margin:0 0 8px}#midpoint-followup h3{font-size:17px;margin:20px 0 8px}#midpoint-followup p{margin:8px 0}#midpoint-followup .mp-muted{color:#526174;font-size:13px}#midpoint-followup .mp-controls{display:flex;gap:14px;flex-wrap:wrap;margin:20px 0}#midpoint-followup label{display:flex;flex-direction:column;font-size:13px;font-weight:600;gap:5px}#midpoint-followup select,#midpoint-followup button{font:inherit;min-height:40px;padding:7px 10px;border:1px solid #a6b7ca;border-radius:5px;background:white;color:#172033}#midpoint-followup :focus-visible{outline:3px solid #0284c7;outline-offset:3px}#midpoint-followup .mp-plots{display:grid;grid-template-columns:1fr 1fr;gap:20px}#midpoint-followup svg{width:100%;height:auto;display:block;background:#f8fafc;border:1px solid #e2e8f0;border-radius:7px}#midpoint-followup .mp-scroll{overflow:auto;margin:16px 0}#midpoint-followup table{width:100%;border-collapse:collapse;font-size:13px;white-space:nowrap}#midpoint-followup th,#midpoint-followup td{text-align:left;padding:10px;border-bottom:1px solid #dbe3ec;vertical-align:top}#midpoint-followup th{background:#edf3f8}#midpoint-followup .mp-banner{border-left:4px solid #0c719e;background:#edf6fb;padding:12px 16px}#midpoint-followup .mp-badge{display:inline-block;border:1px solid #ced9e6;padding:3px 8px;border-radius:20px;font-size:12px;margin-right:7px}#midpoint-followup .mp-c{color:#b91c1c}#midpoint-followup .mp-h{color:#0369a1}#midpoint-followup .mp-actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:14px}@media(max-width:760px){#midpoint-followup{padding:15px}#midpoint-followup .mp-plots{grid-template-columns:1fr}#midpoint-followup .mp-controls>*{flex:1;min-width:130px}}
</style>
<section id="midpoint-followup" aria-labelledby="mp-title">
<h2 id="mp-title">Fresh midpoint and workload-seed checks</h2>
<p class="mp-muted">10 November 2026 · 4 KiB ordinary get · 512 MiB G1 · 50,000 scheduled requests/s · 30-second offered windows</p>
<div id="mp-summary" class="mp-banner" role="status"></div>
<p class="mp-muted">This is a separate follow-up cohort. Historical measurements above retain their original classifications. A ratio below 1 favours Chronicle; ranges are fork ranges, not confidence intervals.</p>
<div class="mp-controls">
<label>Cohort<select id="mp-cohort"></select></label>
<label>Timing channel<select id="mp-channel"><option value="response">Scheduled response</option><option value="service">Service during scheduled arrivals</option><option value="gap">Inter-completion gap</option></select></label>
<label>Percentile<select id="mp-percentile"><option>99</option><option selected>99.9</option><option>99.99</option><option>99.999</option></select></label>
</div>
<div class="mp-plots"><div><h3>Latency at each measured pressure point</h3><div id="mp-latency"></div></div><div><h3>Paired Chronicle / Caffeine ratios</h3><div id="mp-ratios"></div></div></div>
<p class="mp-muted"><span class="mp-c">● Caffeine</span> · <span class="mp-h">● Chronicle</span> · Hollow dots carry warnings. Lines connect observed medians for orientation; they do not locate an exact crossover. Points are keyboard focusable.</p>
<div class="mp-scroll"><table><caption style="text-align:left;font-weight:600">Conclusions at every pressure point in this cohort</caption><thead><tr><th>Ballast</th><th>Caffeine range</th><th>Chronicle range</th><th>Paired ratios</th><th>Observed direction</th><th>Warning-free pairs</th></tr></thead><tbody id="mp-table"></tbody></table></div>
<h3>Full empirical tail and stall probabilities</h3>
<div class="mp-controls"><label>Application ballast<select id="mp-ballast"></select></label><label>Pair<select id="mp-pair"></select></label></div>
<div id="mp-survival"></div><div id="mp-stalls" class="mp-scroll"></div>
<p class="mp-muted">Curves show strict exceedance probabilities at retained HDR bin boundaries. Requested thresholds report definite–possible counts when a bin straddles the threshold. Zero observed events does not establish zero risk. Queued responses can share a pause.</p>
<details><summary>Allocation, GC, resident memory and warnings</summary><div id="mp-resources" class="mp-scroll"></div></details>
<p id="mp-support" class="mp-muted"></p>
<div class="mp-actions"><button id="mp-download-study">Download follow-up dataset</button><button id="mp-download-csv">Download every conclusion</button><button id="mp-download-tails">Download full tails</button></div>
<p id="mp-audit" class="mp-muted"></p>
</section>
<script id="midpoint-data" type="application/json">__MIDPOINT_DATA__</script>
<script>
(()=>{'use strict';
const M=JSON.parse(document.getElementById('midpoint-data').textContent),D=JSON.parse(M.studyText),T=JSON.parse(M.tailsText);
const $=id=>document.getElementById(id),esc=x=>String(x).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const C='CAFFEINE',H='CHRONICLE_IN_MEMORY',color=b=>b===C?'#b91c1c':'#0369a1';
const num=(x,n=3)=>Number.isFinite(x)?Number(x).toLocaleString(undefined,{maximumFractionDigits:n}):'—';
const latency=n=>n==null?'—':n<1000?num(n,0)+' ns':n<1e6?num(n/1000,2)+' µs':num(n/1e6,3)+' ms';
const options=(id,values)=>{$(id).innerHTML=values.map(([v,t])=>`<option value="${esc(v)}">${esc(t)}</option>`).join('')};
const fields=()=>({cohort:$('mp-cohort').value,channel:$('mp-channel').value,p:$('mp-percentile').value});
const selected=()=>D.observations.filter(r=>r.cohort===$('mp-cohort').value);
options('mp-cohort',D.stages.map(s=>[s.label,`${s.label==='primary'?'Primary replication':s.label.startsWith('adaptive')?'Adaptive exploration':'Seed check'} · seed ${s.seed} · ${s.passes} pair${s.passes===1?'':'s'}/point`]));
const primary=D.conclusions.filter(r=>r.cohort==='primary'&&r.channel==='response'&&r.percentile==='99.9');
$('mp-summary').textContent=`${D.observations.length} workload JVMs collected. Primary p99.9 directions: ${primary.map(r=>r.ballastMiB+' MiB: '+r.direction).join('; ')}. ${D.adaptiveDecision}.`;
$('mp-audit').textContent=`Audit: ${M.audit.independentGcChecks} GC reconciliations, ${M.audit.independentThresholdChecks} independent threshold checks, ${M.audit.runtimeFilesVerified} runtime files verified. Dataset SHA-256: ${M.audit.studySha256}`;
function frame(title,rows,ratio=false){
 const small=window.innerWidth<700,w=small?360:620,h=350,l=small?69:76,r=20,t=25,b=56,vs=rows.map(x=>x.v).filter(v=>v>0);
 if(!vs.length)return {empty:'<p>No complete observations for this view.</p>'};
 const min=ratio?Math.min(.1,...vs)/1.2:Math.min(...vs)/1.5,max=Math.max(ratio?1:0,...vs)*1.5;
 const xmin=0,xmax=Math.max(208,...rows.map(x=>x.x));
 const X=x=>l+(x-xmin)/(xmax-xmin)*(w-l-r),Y=v=>h-b-(Math.log10(v)-Math.log10(min))/(Math.log10(max)-Math.log10(min))*(h-b-t);
 let html=`<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(title)}"><title>${esc(title)}</title>`;
 for(let e=Math.ceil(Math.log10(min));e<=Math.floor(Math.log10(max));e++){let v=10**e;html+=`<line x1="${l}" x2="${w-r}" y1="${Y(v)}" y2="${Y(v)}" stroke="#dbe3ec"/><text x="${l-8}" y="${Y(v)+4}" font-size="12" text-anchor="end">${ratio?num(v):latency(v)}</text>`;}
 for(let x of [...new Set([0,104,208,...rows.map(x=>x.x)])].sort((a,b)=>a-b))html+=`<text x="${X(x)}" y="${h-b+21}" font-size="12" text-anchor="middle">${x}</text>`;
 html+=`<text x="${w/2}" y="${h-12}" text-anchor="middle" font-size="13">Common application ballast (MiB)</text>`;
 if(ratio)html+=`<line x1="${l}" x2="${w-r}" y1="${Y(1)}" y2="${Y(1)}" stroke="#64748b" stroke-dasharray="5 4"/>`;
 return {html,X,Y,end:'</svg>'};
}
function draw(){
 const {cohort,channel,p}=fields(),rows=selected(),comparisons=D.conclusions.filter(r=>r.cohort===cohort&&r.channel===channel&&r.percentile===p);
 const dots=rows.filter(r=>r.status==='OK'&&r.latencyVerified).map(r=>({x:r.liveMiB,v:r.latency[channel].percentilesNs[p],r}));
 let f=frame(`${channel} p${p}`,dots);
 if(f.empty)$('mp-latency').innerHTML=f.empty;else{
  for(let b of [C,H]){let med=Object.entries(Object.groupBy(dots.filter(d=>d.r.backend===b),d=>d.x)).map(([x,ds])=>({x:+x,v:ds.map(d=>d.v).sort((a,b)=>a-b)[Math.floor(ds.length/2)]})).sort((a,b)=>a.x-b.x);f.html+=`<polyline fill="none" stroke="${color(b)}" stroke-width="2" points="${med.map(d=>f.X(d.x)+','+f.Y(d.v)).join(' ')}"/>`;}
  for(let d of dots){let note=`${d.r.backend}, ${d.x} MiB, pair ${d.r.block}: ${latency(d.v)}${d.r.warnings.length?'; '+d.r.warnings.join('; '):''}`;f.html+=`<circle tabindex="0" role="img" aria-label="${esc(note)}" cx="${f.X(d.x)}" cy="${f.Y(d.v)}" r="4.5" fill="${d.r.warnings.length?'white':color(d.r.backend)}" stroke="${color(d.r.backend)}" stroke-width="2"><title>${esc(note)}</title></circle>`;} $('mp-latency').innerHTML=(f.html+f.end).replaceAll('font-size="12"',window.innerWidth<700?'font-size="14"':'font-size="12"');
 }
 const ratios=comparisons.flatMap(r=>r.pairedRatios.map((v,i)=>({x:r.ballastMiB,v,block:r.pairedBlocks[i]})));f=frame('Paired Chronicle / Caffeine ratio',ratios,true);
 if(f.empty)$('mp-ratios').innerHTML=f.empty;else{for(let d of ratios){let note=`${d.x} MiB, pair ${d.block}: ${num(d.v,4)}×`;f.html+=`<circle tabindex="0" role="img" aria-label="${esc(note)}" cx="${f.X(d.x)}" cy="${f.Y(d.v)}" r="5" fill="#334155"><title>${esc(note)}</title></circle>`;}$('mp-ratios').innerHTML=f.html+f.end;}
 $('mp-table').innerHTML=comparisons.map(r=>`<tr><td>${r.ballastMiB} MiB</td><td>${r.backendRangesNs[C]?.map(latency).join('–')||'—'}</td><td>${r.backendRangesNs[H]?.map(latency).join('–')||'—'}</td><td>${r.pairedRatios.map(v=>num(v,4)+'×').join(', ')}</td><td>${esc(r.direction)}${r.expectedPairs===1?'<br><small>Single pair; descriptive only</small>':''}</td><td>${r.warningFreePairs}/${r.expectedPairs}<br><small>${esc(r.cleanDirection)} in clean subset</small></td></tr>`).join('');
 const stage=D.stages.find(s=>s.label===cohort),old=$('mp-ballast').value;
 options('mp-ballast',stage.levelsMiB.map(v=>[v,v+' MiB']));if(stage.levelsMiB.map(String).includes(old))$('mp-ballast').value=old;
 options('mp-pair',Array.from({length:stage.passes},(_,i)=>[i+1,'Pair '+(i+1)]));
 $('mp-support').textContent=`${stage.passes} pair${stage.passes===1?'':'s'} per point in this cohort. Each complete response fork contains 1,500,000 requests; p99.999 has about 15 nominal upper-tail observations, not independent pause episodes. All timing channels here come from scheduled-arrival runs.`;
 $('mp-resources').innerHTML='<table><thead><tr><th>Ballast / backend / pair</th><th>Measured RSS maximum</th><th>Post-GC heap median</th><th>GC wall fraction</th><th>Worker B/op</th><th>Warnings</th></tr></thead><tbody>'+rows.map(r=>`<tr><td>${r.liveMiB} MiB / ${r.backend===C?'Caffeine':'Chronicle'} / ${r.block}</td><td>${num((r.processMemory?.measuredMaxRssKiB??NaN)/1024,1)} MiB</td><td>${num((r.gc?.postGcUsedHeapMedianFraction??NaN)*100,1)}%</td><td>${num((r.gc?.pauseExposureFraction??NaN)*100,2)}%</td><td>${num(r.measurement?.workerBytesPerOperation,1)}</td><td style="white-space:normal">${esc(r.warnings.join('; ')||'None')}</td></tr>`).join('')+'</tbody></table><p class="mp-muted">RSS is sampled once per second; it is not PSS, exact native allocation or an equal-total-memory experiment.</p>';
 tail();
}
const cache=new Map();let tailVersion=0;
async function bins(r,channel){let key=r.batch+'/'+r.label+'/'+channel;if(cache.has(key))return cache.get(key);const f=T.forks.find(f=>f.batch===r.batch&&f.label===r.label);if(!f)return null;let encoded=f.channels[channel].curve;let bytes=Uint8Array.from(atob(encoded),c=>c.charCodeAt(0));let stream=new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'));let values=JSON.parse(await new Response(stream).text());cache.set(key,values);return values;}
async function tail(){
 const version=++tailVersion,{channel}=fields(),pair=+$('mp-pair').value,live=+$('mp-ballast').value;
 const chosen=selected().filter(r=>r.liveMiB===live&&r.block===pair&&r.status==='OK'&&r.latencyVerified);if(chosen.length!==2){$('mp-survival').textContent='This pair has incomplete outcomes; no complete tail comparison.';return;}
 $('mp-survival').textContent='Decoding retained distributions…';
 try{let curves=await Promise.all(chosen.map(async r=>({r,values:await bins(r,channel)})));if(version!==tailVersion)return;
 const small=window.innerWidth<700,w=small?360:1000,h=350,l=small?65:88,b=55,t=24,right=25,X=v=>l+(Math.log10(v)-2)/6*(w-l-right),Y=p=>h-b-(Math.log10(p)+7)/7*(h-b-t);
 let html=`<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="Full empirical ${channel} survival probabilities"><title>Full empirical ${channel} survival probabilities at ${live} MiB, pair ${pair}</title>`;
 for(let e=-7;e<=0;e++){let p=10**e;html+=`<line x1="${l}" x2="${w-right}" y1="${Y(p)}" y2="${Y(p)}" stroke="#dbe3ec"/><text x="${l-9}" y="${Y(p)+4}" text-anchor="end" font-size="12">${p.toExponential(0)}</text>`;}
 for(let e=2;e<=8;e+=small?2:1){let v=10**e;html+=`<text x="${X(v)}" y="${h-b+22}" text-anchor="middle" font-size="12">${latency(v)}</text>`;}
 for(let threshold of [1e5,1e6,1e7])html+=`<line x1="${X(threshold)}" x2="${X(threshold)}" y1="${t}" y2="${h-b}" stroke="#94a3b8" stroke-dasharray="4 4"/>`;
 for(let {r,values} of curves){if(!values)continue;let n=r.latency[channel].count,sum=0,points=[];for(let i=0;i<values.length;i+=2){sum+=values[i+1];let p=(n-sum)/n;if(values[i]>=100&&values[i]<=1e8&&p>0)points.push(X(values[i])+','+Y(p));}html+=`<polyline fill="none" stroke="${color(r.backend)}" stroke-width="1.8" points="${points.join(' ')}"><title>${r.backend}; N=${n}</title></polyline>`;}
 html+=`<text x="${w/2}" y="${h-9}" text-anchor="middle" font-size="13">Latency; P(latency &gt; x), both log scales</text></svg>`;$('mp-survival').innerHTML=html;
 let table='<table><thead><tr><th>Strict threshold</th><th>Caffeine exceedances / requests</th><th>Chronicle exceedances / requests</th></tr></thead><tbody>';
 for(let threshold of ['100000','1000000','10000000']){table+=`<tr><td>&gt; ${latency(+threshold)}</td>`;for(let b of [C,H]){let r=chosen.find(r=>r.backend===b),v=r.stallRates[channel],q=v.rates[threshold];table+=`<td>${q.lowerCount===q.upperCount?num(q.lowerCount,0):num(q.lowerCount,0)+'–'+num(q.upperCount,0)} / ${num(v.count,0)}<br>${num(q.lowerProbability*100,6)}${q.lowerProbability===q.upperProbability?'':'–'+num(q.upperProbability*100,6)}%</td>`;}table+='</tr>';}$('mp-stalls').innerHTML=table+'</tbody></table>';
 }catch(error){$('mp-survival').textContent='Curve decoding is unavailable in this browser. Download the full tails; numerical conclusions remain available.';console.error(error);}
}
for(let id of ['mp-cohort','mp-channel','mp-percentile'])$(id).addEventListener('change',draw);
for(let id of ['mp-ballast','mp-pair'])$(id).addEventListener('change',tail);
function download(name,text,mime){let url=URL.createObjectURL(new Blob([text],{type:mime})),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),60000);}
$('mp-download-study').onclick=()=>download('tailcache-midpoint-study.json',M.studyText,'application/json');
$('mp-download-csv').onclick=()=>download('tailcache-midpoint-conclusions.csv',M.conclusionsCsv,'text/csv');
$('mp-download-tails').onclick=()=>download('tailcache-midpoint-tails.json',M.tailsText,'application/json');
draw();
})();
</script>
'''


def render_component():
    study=(DATA/'study.json').read_text();tails=(DATA/'tails.json').read_text()
    packet=dict(audit=json.loads((DATA/'audit.json').read_text()),studyText=study,tailsText=tails,conclusionsCsv=(DATA/'conclusions.csv').read_bytes().decode())
    embedded=json.dumps(packet,separators=(',',':')).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    return START+PANEL.replace('__MIDPOINT_DATA__',embedded)+END


def attach(page,component):
    page=re.sub(re.escape(START)+'.*?'+re.escape(END),'',page,flags=re.S)
    assert '<footer class="footer">' in page
    page=page.replace('<footer class="footer">',component+'<footer class="footer">',1)
    if 'id="midpoint-jump"' not in page:
        marker='<main class="wrap">'
        assert marker in page
        page=page.replace(marker,marker+'<p id="midpoint-jump" style="margin-top:18px"><a href="#midpoint-followup">New: midpoint and independent workload-seed results →</a></p>',1)
    return page


def main():
    component=render_component()
    out=ROOT/'docs/TAILCACHE_MIDPOINT_EXPLORER.html'
    out.write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>TailCache midpoint follow-up</title></head><body style="margin:auto;max-width:1450px;padding:15px;background:#f1f5f9">'+component+'</body></html>')
    original=ROOT/'docs/TAILCACHE_RESULTS_EXPLORER.html';page=original.read_text()
    original.write_text(attach(page,component))
    print(json.dumps(dict(standalone=str(out),integrated=str(original),bytes=original.stat().st_size,sha256=hashlib.sha256(original.read_bytes()).hexdigest()),indent=2))


if __name__=='__main__':main()
