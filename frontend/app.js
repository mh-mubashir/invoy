const api = {
  base: location.origin.replace(/\/$/, ''),
  async allocate({ client, total_hours, freeform }){
    const res = await fetch(`${this.base}/ai-invoice/allocate`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ client, total_hours, freeform })});
    if(!res.ok) throw new Error('allocate failed');
    return res.json();
  },
  async stt(file){
    const fd=new FormData(); fd.append('file',file);
    const res=await fetch(`${this.base}/stt`,{method:'POST',body:fd});
    if(!res.ok) throw new Error('stt failed');
    return res.json();
  }
};

const messagesEl=document.getElementById('messages');
function addMsg(role, html){
  const el=document.createElement('div'); el.className=`msg ${role}`; el.innerHTML=html; messagesEl.appendChild(el); messagesEl.scrollTop=messagesEl.scrollHeight;
}

async function onSend(){
  const client=document.getElementById('client').value||null;
  const hours=parseFloat(document.getElementById('hours').value||'')||null;
  const text=document.getElementById('input').value.trim();
  if(!text){ return; }
  addMsg('user', text.replace(/
/g,'<br>'));
  document.getElementById('input').value='';
  addMsg('ai', 'Thinking…');
  try{
    const data=await api.allocate({ client, total_hours: hours, freeform: text });
    const rows=(data.line_items||[]).map(li=>`<tr><td>${li.subject}</td><td>${li.justification||''}</td><td style="text-align:right">${li.estimated_hours.toFixed(1)}</td></tr>`).join('');
    const table=`<div><strong>Client:</strong> ${data.client_name} &nbsp; <strong>Total hours:</strong> ${data.total_hours_billed.toFixed(1)}</div><table style="width:100%;border-collapse:collapse;margin-top:8px"><thead><tr><th style="text-align:left">Subject</th><th style="text-align:left">Justification</th><th style="text-align:right;width:90px">Hours</th></tr></thead><tbody>${rows}</tbody></table>`;
    addMsg('ai', table);
  }catch(e){ addMsg('ai', 'Failed to allocate.'); }
}

document.getElementById('send').addEventListener('click', onSend);

// Mic handling
let mediaRecorder, chunks=[];
async function onMic(){
  if(!mediaRecorder){
    const stream=await navigator.mediaDevices.getUserMedia({audio:true});
    mediaRecorder=new MediaRecorder(stream);
    mediaRecorder.ondataavailable=(e)=>{ if(e.data.size) chunks.push(e.data); };
    mediaRecorder.onstop=async()=>{
      const blob=new Blob(chunks,{type:'audio/webm'}); chunks=[];
      addMsg('user','[Voice note captured]');
      try{ const {text}=await api.stt(new File([blob],'note.webm',{type:'audio/webm'})); document.getElementById('input').value = (document.getElementById('input').value+'
'+text).trim(); }catch(e){ addMsg('ai','STT failed.'); }
    };
  }
  if(mediaRecorder.state==='recording'){ mediaRecorder.stop(); this.textContent='🎙️'; }
  else { mediaRecorder.start(); this.textContent='⏹️'; }
}

document.getElementById('mic').addEventListener('click', onMic);
