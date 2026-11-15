PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Drumless</title>
<style>
:root{--bg:#f5f5f5;--card:#fff;--text:#222;--mute:#777;--line:#e2e2e2;--accent:#3367d6;--err:#c0392b;--ok:#2e7d32}
@media(prefers-color-scheme:dark){:root{--bg:#131313;--card:#2b2b2b;--text:#eaeaea;--mute:#999;--line:#404040;--accent:#5a95f5;--err:#ff7b6b;--ok:#6fcf7a}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:16px/1.4 system-ui,sans-serif}
main{max-width:760px;margin:0 auto;padding:16px}
h1{font-size:1.4rem;margin:8px 0 2px}.sub{color:var(--mute);margin:0 0 16px}
.card{background:var(--card);border-radius:8px;padding:14px;margin-bottom:12px;box-shadow:0 1px 3px #0002}
#drop{border:2px dashed var(--line);text-align:center;padding:28px 12px;cursor:pointer}
#drop.over{border-color:var(--accent)}
#drop small{display:block;color:var(--mute);margin-top:4px}
.acts{display:flex;gap:12px;align-items:center}
.row{display:flex;gap:8px;align-items:center;justify-content:space-between;flex-wrap:wrap}
.st{font-size:.8rem;color:var(--mute)}.st.done{color:var(--ok)}.st.error{color:var(--err)}
.disc{width:100%;aspect-ratio:1;border-radius:50%;background:
 radial-gradient(circle,var(--card) 0 9%,#0004 9% 10%,transparent 10.5%),
 repeating-radial-gradient(circle,#0000 0 3px,#0000001a 3px 4px),
 conic-gradient(hsl(var(--h) 65% 48%),hsl(var(--h) 75% 70%),hsl(var(--h) 60% 38%),hsl(var(--h) 75% 66%),hsl(var(--h) 65% 48%))}
.disc.busy{opacity:.4}
#list{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px}
#list>.sub{grid-column:1/-1;margin:0}
.tile{position:relative;aspect-ratio:1;overflow:hidden;background:var(--card);border-radius:10px;padding:10px;display:flex;flex-direction:column;align-items:center;border:2px solid transparent;box-shadow:0 1px 3px #0002;min-width:0}
.tile .disc{width:58%;flex:none}
.tile.pick,.tile.bad{cursor:pointer}.tile.pick:hover{border-color:var(--line)}
.tile.sel{border-color:var(--accent)}
.tname{margin-top:6px;width:100%;font-size:.85rem;font-weight:600;line-height:1.2;text-align:center;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow-wrap:anywhere}
.tile .st{margin-top:2px;text-align:center}
.x{position:absolute;top:4px;right:6px;color:var(--mute);font-size:.9rem;padding:2px 4px}
#player .head{display:flex;gap:14px;align-items:center}
#pdisc{width:64px;flex:none}
.tt{flex:1;min-width:0}
.ptitle{font-size:1.15rem;font-weight:700;overflow-wrap:anywhere}
.pstem{color:var(--mute);font-size:.85rem}
.seg{display:grid;grid-template-columns:repeat(3,1fr);margin-top:16px;border:1px solid var(--line);border-radius:8px;overflow:hidden}
.seg button{padding:10px 6px;font-weight:600;color:var(--mute);border-right:1px solid var(--line)}
.seg button:last-child{border-right:0}
.seg button.on{background:var(--accent);color:#fff}
.seek{display:flex;gap:10px;align-items:center;margin-top:16px;font-size:.85rem;color:var(--mute);font-variant-numeric:tabular-nums}
.seek input{flex:1;min-width:0;accent-color:var(--accent)}
.transport{display:flex;justify-content:center;align-items:center;gap:28px;margin-top:8px}
#play{width:64px;height:64px;border-radius:50%;background:var(--accent);color:#fff;font-size:1.4rem}
.skip{color:var(--text);border:1px solid var(--line)!important;border-radius:20px;padding:8px 14px}
.rates{display:flex;gap:6px;align-items:center;margin-top:16px}
.rates span{color:var(--mute);font-size:.75rem;letter-spacing:.08em;margin-right:4px}
.rates button{flex:1;border:1px solid var(--line);border-radius:6px;padding:8px 0;color:var(--text);font-weight:600}
.rates button.on{background:var(--accent);border-color:var(--accent);color:#fff}
.seg button:hover,.rates button:hover,#play:hover,.skip:hover{text-decoration:none}
#play:hover{filter:brightness(1.12)}
#dl{margin-top:14px;font-size:.9rem}#dl summary{color:var(--accent);cursor:pointer}
#dl .links{flex-direction:column;gap:6px}
@keyframes spin{to{transform:rotate(360deg)}}
body.playing #pdisc{animation:spin 4s linear infinite}
#player{border:2px solid var(--accent)}
a,button{color:var(--accent);background:none;border:0;font:inherit;cursor:pointer;padding:0;text-decoration:none}
a:hover,button:hover{text-decoration:underline}
.links{display:flex;gap:14px;margin-top:8px;flex-wrap:wrap;font-size:.9rem}
.err{color:var(--err);font-size:.85rem;overflow-wrap:anywhere}
#logbar{position:fixed;left:0;right:0;bottom:0;background:var(--card);border-top:1px solid var(--line);box-shadow:0 -2px 6px #0002}
#logbar[hidden]{display:none}
#logbar .row{max-width:760px;margin:0 auto;padding:6px 16px;font-size:.85rem}
#logbar .row span{color:var(--mute);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
#log{margin:0;height:11rem;overflow:auto;padding:0 16px 8px;font:12px/1.35 ui-monospace,monospace;white-space:pre-wrap;overflow-wrap:anywhere}
#logbar.min #log,#logbar.min #loghandle{display:none}
#loghandle{height:10px;cursor:ns-resize;touch-action:none;display:flex;align-items:center;justify-content:center}
#loghandle::after{content:"";width:40px;height:4px;border-radius:2px;background:var(--line)}
#loghandle:hover::after,#loghandle.drag::after{background:var(--mute)}
</style></head><body><main>
<h1>Drumless</h1><p class="sub">Upload a song, get it back without the drums. <span id="model"></span></p>
<div class="card" id="drop"><input id="file" type="file" accept="audio/*,.flac,.m4a,.opus" multiple hidden>
Drop songs here or click to choose<small>mp3, wav, flac, m4a, ogg … up to 500 MB each</small></div>
<div id="msg" class="err"></div>
<div class="card" id="player" hidden>
 <div class="head"><div class="disc" id="pdisc"></div>
  <div class="tt"><div class="ptitle" id="pname"></div><div class="pstem" id="pstem"></div></div>
  <span class="acts"><button id="pren">Rename</button><button id="pdel">Delete</button></span></div>
 <div class="seg" id="stems"><button data-stem="no_drums">Without drums</button><button data-stem="drums">Drums only</button><button data-stem="original">Original</button></div>
 <div class="seek"><span id="pos">0:00</span><input id="seek" type="range" min="0" max="1" step="0.1" value="0" aria-label="Seek"><span id="tot">0:00</span></div>
 <div class="transport"><button class="skip" id="back">⏪ 10s</button><button id="play" aria-label="Play">▶</button><button class="skip" id="fwd">10s ⏩</button></div>
 <div class="rates" id="rates"><span>SPEED</span><button data-rate="50">50</button><button data-rate="60">60</button><button data-rate="70">70</button><button data-rate="80">80</button><button data-rate="90">90</button><button data-rate="100">100</button></div>
 <details id="dl"><summary>Download</summary><div class="links" id="plinks"></div></details>
 <audio id="audio" preload="auto"></audio>
</div>
<div id="list"></div>
</main>
<div id="logbar" hidden><div id="loghandle" title="Drag to resize"></div><div class="row"><span id="logname"></span><button id="logtoggle">Hide log</button></div><pre id="log"></pre></div>
<script>
const $=s=>document.querySelector(s), esc=s=>s.replace(/[&<>"']/g,c=>"&#"+c.charCodeAt(0)+";");
const LABEL={queued:"Queued",separating:"Separating…",mixing:"Mixing…",done:"Done",error:"Failed",cancelled:"Cancelled"};
function elapsed(t){const s=Math.max(0,Math.round(Date.now()/1000-t));return Math.floor(s/60)+"m "+String(s%60).padStart(2,"0")+"s"}
const STEMS={no_drums:"Without drums",drums:"Drums only",original:"Original"};
const fmt=x=>{if(!isFinite(x))return"0:00";x=Math.floor(x);return Math.floor(x/60)+":"+String(x%60).padStart(2,"0")};
const hue=n=>{let h=0;for(const c of n)h=(h*31+c.charCodeAt(0))%360;return h};
let tracks=[],cur=null,stem="no_drums",rate=1,dragging=false;
try{rate=+localStorage.getItem("rate")||1}catch(e){}
const audio=$("#audio");
audio.preservesPitch=audio.webkitPreservesPitch=true;
function tile(t){
  const run=t.status==="separating"||t.status==="mixing",done=t.status==="done";
  const st=done?"":LABEL[t.status]+(t.status==="queued"&&t.position?` (#${t.position})`:"")+(run?" · "+elapsed(t.started):"");
  const x=run?`<button class="x" data-cancel="${t.id}" title="Cancel" aria-label="Cancel">✕</button>`:done?"":`<button class="x" data-del="${t.id}" title="Delete" aria-label="Delete">✕</button>`;
  const cls=["tile",done&&"pick",t.status==="error"&&"bad",t.id===cur&&"sel"].filter(Boolean).join(" ");
  return `<div class="${cls}" data-id="${t.id}" data-err="${esc(t.error||"")}" style="--h:${hue(t.name)}">${x}
   <div class="disc${done?"":" busy"}"></div><div class="tname">${esc(t.name)}</div><div class="st ${t.status}">${st}</div></div>`;
}
function setRate(r){
  rate=r;audio.defaultPlaybackRate=audio.playbackRate=r;
  document.querySelectorAll("#rates button").forEach(b=>b.classList.toggle("on",+b.dataset.rate===Math.round(r*100)));
  try{localStorage.setItem("rate",r)}catch(e){}
}
function showStem(keepPos){
  const pos=audio.currentTime,was=!audio.paused;
  audio.src=`/files/${cur}/${stem}`;
  if(keepPos)audio.addEventListener("loadedmetadata",()=>{audio.currentTime=pos;if(was)audio.play().catch(()=>{})},{once:true});
  else{$("#seek").value=0;$("#pos").textContent="0:00"}
  setRate(rate);
  $("#pstem").textContent=STEMS[stem];
  document.querySelectorAll("#stems button").forEach(b=>b.classList.toggle("on",b.dataset.stem===stem));
}
function select(id){
  cur=id;stem="no_drums";$("#player").hidden=false;
  $("#plinks").innerHTML=Object.entries(STEMS).map(([k,l])=>`<a href="/files/${id}/${k}?dl=1">${l}</a>`).join("");
  $("#dl").open=false;showStem(false);syncPlayer();
  $("#player").scrollIntoView({behavior:"smooth",block:"nearest"});
}
function syncPlayer(){
  const t=tracks.find(t=>t.id===cur);
  if(!t){if(cur){cur=null;audio.pause();audio.removeAttribute("src");audio.load()}$("#player").hidden=true;return}
  $("#pname").textContent=t.name;$("#pdisc").style.setProperty("--h",hue(t.name));
}
async function refresh(){
  try{
    const d=await (await fetch("/api/tracks")).json();
    $("#model").textContent="Model: "+d.model.replace(/\.(yaml|ckpt)$/,"");
    tracks=d.tracks;
    const sig=JSON.stringify([cur,d.tracks.map(t=>[t.id,t.name,t.status,t.position])]);
    if(sig!==refresh.sig||d.tracks.some(t=>t.status==="separating"||t.status==="mixing")){
      $("#list").innerHTML=d.tracks.map(tile).join("")||'<p class="sub">No tracks yet.</p>';refresh.sig=sig;
    }
    syncPlayer();
  }catch(e){}
}
audio.onloadedmetadata=()=>{$("#seek").max=audio.duration;$("#tot").textContent=fmt(audio.duration)};
audio.ontimeupdate=()=>{if(!dragging)$("#seek").value=audio.currentTime;$("#pos").textContent=fmt(audio.currentTime)};
audio.onplay=audio.onpause=audio.onended=()=>{
  const p=!audio.paused&&!audio.ended;
  document.body.classList.toggle("playing",p);
  $("#play").textContent=p?"❚❚":"▶";$("#play").setAttribute("aria-label",p?"Pause":"Play");
};
async function refreshLog(){
  try{
    const d=await (await fetch("/api/log")).json();
    const bar=$("#logbar"),pre=$("#log");
    bar.hidden=!d.id;
    // Leave room at the bottom of the page so the panel never covers the last card.
    document.body.style.paddingBottom=d.id?bar.offsetHeight+"px":"";
    if(!d.id)return;
    $("#logname").textContent="Log · "+d.name;
    const stick=pre.scrollTop+pre.clientHeight>=pre.scrollHeight-24;
    const text=d.lines.join("\n");
    if(pre.textContent!==text){pre.textContent=text;if(stick||refreshLog.id!==d.id)pre.scrollTop=pre.scrollHeight}
    refreshLog.id=d.id;
  }catch(e){}
}
// Drag the handle on the panel's top edge to resize the log; the height is remembered.
const logH=()=>$("#log").getBoundingClientRect().height;
function setLogH(px){
  px=Math.max(60,Math.min(px,innerHeight*0.8));
  $("#log").style.height=px+"px";
  document.body.style.paddingBottom=$("#logbar").offsetHeight+"px";
  return px;
}
try{const h=+localStorage.getItem("logH");if(h)setLogH(h)}catch(e){}
$("#loghandle").onpointerdown=e=>{
  const handle=e.currentTarget,y0=e.clientY,h0=logH();let h=h0;
  handle.setPointerCapture(e.pointerId);handle.classList.add("drag");e.preventDefault();
  handle.onpointermove=m=>{h=setLogH(h0+y0-m.clientY)};
  handle.onpointerup=handle.onpointercancel=()=>{
    handle.onpointermove=handle.onpointerup=handle.onpointercancel=null;handle.classList.remove("drag");
    try{localStorage.setItem("logH",Math.round(h))}catch(e){}
  };
};
$("#logtoggle").onclick=()=>{
  const bar=$("#logbar");bar.classList.toggle("min");
  $("#logtoggle").textContent=bar.classList.contains("min")?"Show log":"Hide log";
  document.body.style.paddingBottom=bar.offsetHeight+"px";
};
async function upload(files){
  for(const f of files){
    const fd=new FormData();fd.append("file",f);
    $("#msg").textContent=`Uploading ${f.name}…`;
    const r=await fetch("/api/upload",{method:"POST",body:fd});
    if(!r.ok){const j=await r.json().catch(()=>({}));$("#msg").textContent=`${f.name}: ${j.detail||r.status}`;return}
  }
  $("#msg").textContent="";refresh();
}
const drop=$("#drop");
drop.onclick=()=>$("#file").click();
$("#file").onchange=e=>{upload([...e.target.files]);e.target.value=""};
drop.ondragover=e=>{e.preventDefault();drop.classList.add("over")};
drop.ondragleave=()=>drop.classList.remove("over");
drop.ondrop=e=>{e.preventDefault();drop.classList.remove("over");upload([...e.dataTransfer.files])};
async function del(id){
  if(!confirm("Delete this track and its files?"))return;
  await fetch("/api/tracks/"+id,{method:"DELETE"});refresh.sig=null;refresh();
}
$("#list").onclick=async e=>{
  const id=e.target.dataset.del,cid=e.target.dataset.cancel;
  if(id)return del(id);
  if(cid){if(confirm("Cancel processing this track?")){await fetch("/api/tracks/"+cid+"/cancel",{method:"POST"});refresh.sig=null;refresh()}return}
  const bad=e.target.closest(".bad");
  if(bad){$("#msg").textContent=bad.querySelector(".tname").textContent+": "+(bad.dataset.err||"failed");return}
  const row=e.target.closest(".pick");
  if(row&&row.dataset.id!==cur){select(row.dataset.id);refresh.sig=null;refresh()}
};
$("#pdel").onclick=()=>del(cur);
$("#pren").onclick=async()=>{
  const t=tracks.find(t=>t.id===cur);if(!t)return;
  const n=prompt("Rename track",t.name);
  if(!n||!n.trim()||n.trim()===t.name)return;
  const r=await fetch("/api/tracks/"+cur+"/rename",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({name:n.trim()})});
  if(!r.ok){const j=await r.json().catch(()=>({}));$("#msg").textContent="Rename: "+(j.detail||r.status)}
  refresh.sig=null;refresh();
};
$("#stems").onclick=e=>{const k=e.target.dataset.stem;if(k&&k!==stem){stem=k;showStem(true)}};
$("#rates").onclick=e=>{const r=e.target.dataset.rate;if(r)setRate(r/100)};
$("#play").onclick=()=>audio.paused?audio.play().catch(()=>{}):audio.pause();
$("#back").onclick=()=>{audio.currentTime=Math.max(0,audio.currentTime-10)};
$("#fwd").onclick=()=>{audio.currentTime=Math.min(audio.duration||1e9,audio.currentTime+10)};
const seek=$("#seek");
seek.oninput=()=>{audio.currentTime=+seek.value;$("#pos").textContent=fmt(+seek.value)};
seek.onpointerdown=()=>{dragging=true};
seek.onpointerup=seek.onpointercancel=()=>{dragging=false};
$("#plinks").onclick=()=>{$("#dl").open=false};
document.addEventListener("keydown",e=>{
  if(e.code==="Space"&&cur&&!["INPUT","BUTTON","SUMMARY","TEXTAREA"].includes(e.target.tagName)){e.preventDefault();$("#play").click()}
});
setRate(rate);
refresh();refreshLog();setInterval(refresh,3000);setInterval(refreshLog,2000);
</script></body></html>
"""
