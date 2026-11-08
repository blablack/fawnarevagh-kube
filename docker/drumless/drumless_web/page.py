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
.row{display:flex;gap:8px;align-items:center;justify-content:space-between;flex-wrap:wrap}
.name{font-weight:600;overflow-wrap:anywhere}
.st{font-size:.85rem;color:var(--mute)}.st.done{color:var(--ok)}.st.error{color:var(--err)}
audio{width:100%;margin-top:8px}
.lbl{font-size:.8rem;color:var(--mute);margin-top:8px}
a,button{color:var(--accent);background:none;border:0;font:inherit;cursor:pointer;padding:0;text-decoration:none}
a:hover,button:hover{text-decoration:underline}
.links{display:flex;gap:14px;margin-top:8px;flex-wrap:wrap;font-size:.9rem}
progress{width:100%;height:6px;margin-top:8px}
.err{color:var(--err);font-size:.85rem;overflow-wrap:anywhere}
</style></head><body><main>
<h1>Drumless</h1><p class="sub">Upload a song, get it back without the drums. <span id="model"></span></p>
<div class="card" id="drop"><input id="file" type="file" accept="audio/*,.flac,.m4a,.opus" multiple hidden>
Drop songs here or click to choose<small>mp3, wav, flac, m4a, ogg … up to 500 MB each</small></div>
<div id="msg" class="err"></div>
<div id="list"></div>
</main>
<script>
const $=s=>document.querySelector(s), esc=s=>s.replace(/[&<>"']/g,c=>"&#"+c.charCodeAt(0)+";");
const LABEL={queued:"Queued",separating:"Separating…",mixing:"Mixing…",done:"Done",error:"Failed"};
function elapsed(t){const s=Math.max(0,Math.round(Date.now()/1000-t));return Math.floor(s/60)+"m "+String(s%60).padStart(2,"0")+"s"}
function card(t){
  const run=t.status==="separating"||t.status==="mixing";
  let st=LABEL[t.status]+(t.status==="queued"&&t.position?` (#${t.position})`:"")+(run?" · "+elapsed(t.started):"");
  let body="";
  if(run||t.status==="queued")body="<progress></progress>";
  if(t.status==="error")body=`<div class="err">${esc(t.error||"")}</div>`;
  if(t.status==="done")body=`<div class="lbl">Without drums</div><audio controls preload="none" src="/files/${t.id}/no_drums"></audio>
   <div class="links"><a href="/files/${t.id}/no_drums?dl=1">Download without drums</a>
   <a href="/files/${t.id}/drums?dl=1">Drums only</a><a href="/files/${t.id}/original?dl=1">Original</a></div>`;
  const del=run?"":`<button data-del="${t.id}">Delete</button>`;
  return `<div class="card" data-id="${t.id}"><div class="row"><span class="name">${esc(t.name)}</span>${del}</div>
   <div class="st ${t.status}">${st}</div>${body}</div>`;
}
async function refresh(){
  try{
    const d=await (await fetch("/api/tracks")).json();
    $("#model").textContent="Model: "+d.model.replace(".yaml","");
    const list=$("#list");
    // Don't rebuild cards while a player is in use, or playback would restart.
    const playing=[...list.querySelectorAll("audio")].some(a=>!a.paused);
    const sig=JSON.stringify(d.tracks.map(t=>[t.id,t.status,t.position]));
    if(!playing&&(sig!==refresh.sig||d.tracks.some(t=>t.status==="separating"||t.status==="mixing"))){
      list.innerHTML=d.tracks.map(card).join("")||'<p class="sub">No tracks yet.</p>';refresh.sig=sig;
    }
  }catch(e){}
}
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
$("#list").onclick=async e=>{
  const id=e.target.dataset.del;
  if(id&&confirm("Delete this track and its files?")){await fetch("/api/tracks/"+id,{method:"DELETE"});refresh.sig=null;refresh()}
};
refresh();setInterval(refresh,3000);
</script></body></html>
"""
