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
.acts{display:flex;gap:12px}
.row{display:flex;gap:8px;align-items:center;justify-content:space-between;flex-wrap:wrap}
.name{font-weight:600;overflow-wrap:anywhere}
.st{font-size:.85rem;color:var(--mute)}.st.done{color:var(--ok)}.st.error{color:var(--err)}
audio{width:100%;margin-top:10px}
.seg{display:flex;gap:6px;margin-top:10px;flex-wrap:wrap}
.seg button{border:1px solid var(--line);border-radius:6px;padding:6px 12px;color:var(--text)}
.seg button.on{background:var(--accent);border-color:var(--accent);color:#fff}
.seg button:hover{text-decoration:none;border-color:var(--accent)}
.speed{display:flex;gap:10px;align-items:center;margin-top:10px;font-size:.9rem}
.speed input{flex:1;min-width:0}.speed b{min-width:3.2em;text-align:right;font-weight:600}
#player{border:2px solid var(--accent)}
.item{display:flex;gap:10px;align-items:center;justify-content:space-between;padding:10px 4px;border-top:1px solid var(--line)}
.item:first-child{border-top:0}
.item.pick{cursor:pointer}.item.pick:hover .name{color:var(--accent)}
.item.sel .name{color:var(--accent)}
.item .st{white-space:nowrap}
.lbl{font-size:.8rem;color:var(--mute);margin-top:8px}
a,button{color:var(--accent);background:none;border:0;font:inherit;cursor:pointer;padding:0;text-decoration:none}
a:hover,button:hover{text-decoration:underline}
.links{display:flex;gap:14px;margin-top:8px;flex-wrap:wrap;font-size:.9rem}
progress{width:100%;height:6px;margin-top:8px}
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
 <div class="row"><span class="name" id="pname"></span><span class="acts"><button id="pren">Rename</button><button id="pdel">Delete</button></span></div>
 <div class="seg" id="stems"><button data-stem="no_drums">Without drums</button><button data-stem="drums">Drums only</button><button data-stem="original">Original</button></div>
 <audio id="audio" controls preload="auto"></audio>
 <div class="speed"><span>Speed</span><input id="rate" type="range" min="50" max="100" step="5" value="100"><b id="rateval">100%</b></div>
 <div class="links" id="plinks"></div>
</div>
<div class="card" id="list"></div>
</main>
<div id="logbar" hidden><div id="loghandle" title="Drag to resize"></div><div class="row"><span id="logname"></span><button id="logtoggle">Hide log</button></div><pre id="log"></pre></div>
<script>
const $=s=>document.querySelector(s), esc=s=>s.replace(/[&<>"']/g,c=>"&#"+c.charCodeAt(0)+";");
const LABEL={queued:"Queued",separating:"Separating…",mixing:"Mixing…",done:"Done",error:"Failed",cancelled:"Cancelled"};
function elapsed(t){const s=Math.max(0,Math.round(Date.now()/1000-t));return Math.floor(s/60)+"m "+String(s%60).padStart(2,"0")+"s"}
let tracks=[],cur=null,stem="no_drums";
const audio=$("#audio");
audio.preservesPitch=audio.webkitPreservesPitch=true;
function item(t){
  const run=t.status==="separating"||t.status==="mixing";
  const st=LABEL[t.status]+(t.status==="queued"&&t.position?` (#${t.position})`:"")+(run?" · "+elapsed(t.started):"");
  const act=run?`<button data-cancel="${t.id}">Cancel</button>`:t.status==="done"?"":`<button data-del="${t.id}">Delete</button>`;
  const err=t.status==="error"&&t.error?`<div class="err">${esc(t.error)}</div>`:"";
  return `<div class="item${t.status==="done"?" pick":""}${t.id===cur?" sel":""}" data-id="${t.id}"><div><div class="name">${esc(t.name)}</div>${err}</div>
   <span class="acts"><span class="st ${t.status}">${st}</span>${act}</span></div>`;
}
function showStem(keepPos){
  const pos=audio.currentTime,was=!audio.paused;
  audio.src=`/files/${cur}/${stem}`;
  if(keepPos)audio.addEventListener("loadedmetadata",()=>{audio.currentTime=pos;if(was)audio.play().catch(()=>{})},{once:true});
  applyRate();
  document.querySelectorAll("#stems button").forEach(b=>b.classList.toggle("on",b.dataset.stem===stem));
}
function applyRate(){
  const r=$("#rate").value/100;
  audio.defaultPlaybackRate=audio.playbackRate=r;
  $("#rateval").textContent=$("#rate").value+"%";
}
function select(id){
  cur=id;stem="no_drums";$("#player").hidden=false;
  $("#plinks").innerHTML=["no_drums|Without drums","drums|Drums only","original|Original"].map(x=>{const[k,l]=x.split("|");return `<a href="/files/${id}/${k}?dl=1">Download ${l.toLowerCase()}</a>`}).join("");
  showStem(false);syncPlayer();
}
function syncPlayer(){
  const t=tracks.find(t=>t.id===cur);
  if(!t){if(cur){cur=null;audio.pause();audio.removeAttribute("src");audio.load()}$("#player").hidden=true;return}
  $("#pname").textContent=t.name;
}
async function refresh(){
  try{
    const d=await (await fetch("/api/tracks")).json();
    $("#model").textContent="Model: "+d.model.replace(/\.(yaml|ckpt)$/,"");
    tracks=d.tracks;
    const sig=JSON.stringify([cur,d.tracks.map(t=>[t.id,t.name,t.status,t.position])]);
    if(sig!==refresh.sig||d.tracks.some(t=>t.status==="separating"||t.status==="mixing")){
      $("#list").innerHTML=d.tracks.map(item).join("")||'<p class="sub" style="margin:0">No tracks yet.</p>';refresh.sig=sig;
    }
    syncPlayer();
  }catch(e){}
}
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
$("#rate").oninput=applyRate;
refresh();refreshLog();setInterval(refresh,3000);setInterval(refreshLog,2000);
</script></body></html>
"""
