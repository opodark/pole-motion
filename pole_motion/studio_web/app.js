const $ = id => document.getElementById(id);
const video = $('video');
const edges = [[11,12],[11,13],[13,15],[12,14],[14,16],[11,23],[12,24],[23,24],[23,25],[25,27],[24,26],[26,28],[27,29],[29,31],[28,30],[30,32]];
const parts = {left_hand:'mano sinistra',right_hand:'mano destra',left_foot:'piede sinistro',right_foot:'piede destro'};
let liveSession=null;
let liveStream=null, livePending=false, livePoints=null, liveUpdated=0, liveEpoch=0;
const livePicture=document.createElement('canvas');
let file = null, documentData = null, recording = null, objectUrl = null, busy = false, generation = 0, sourceHash = null;
const stamp = n => { n = Number.isFinite(n) ? n : 0; return `${Math.floor(n/60).toString().padStart(2,'0')}:${(n%60).toFixed(1).padStart(4,'0')}`; };
function status(message, kind='') { $('status').textContent=message; $('status').className=`status ${kind}`; }
function controls() { const ready=!liveStream&&!livePending&&!!file && Number.isFinite(video.duration); for(const id of ['play','back','forward','seek']) $(id).disabled=!ready; $('analyze').disabled=!ready||busy; $('import-json').disabled=!ready||busy; $('open').disabled=busy||!!liveStream||livePending; $('camera').disabled=busy||!!liveStream||livePending; $('export').disabled=!documentData; }
async function loadVideo(selected) {
  if(!selected||busy||liveStream||livePending)return;
  if(selected.size>1024**3){status('Il video supera il limite di 1 GB. Scegli un estratto più breve.','error');return;}
  LiveEffects.reset();generation++; file=selected; sourceHash=null; documentData=null; recording=null;
  video.pause(); if(objectUrl)URL.revokeObjectURL(objectUrl); objectUrl=file.archiveId?null:URL.createObjectURL(file); video.src=file.archiveId?'/api/library/'+file.archiveId+'/video':objectUrl;
  $('empty').hidden=true; $('stage').classList.add('loaded'); $('session-name').textContent=file.name;
  $('session-meta').textContent=`${(file.size/1024**2).toFixed(1)} MB · Video locale`;
  $('badge').textContent='Video caricato'; $('coverage').textContent='—'; $('holds-total').textContent='—';
  $('hold-count').textContent='—'; $('hold-track').replaceChildren(); $('moments').replaceChildren();
  $('frame-state').textContent='Pronto per l’analisi'; $('frame-detail').textContent='Avvia il rilevamento o carica il JSON di questo video.';
  void restoreSavedAnalysis(selected,generation);
  status('Video caricato. Puoi riprodurlo o avviare l’analisi.'); controls(); draw();
}
$('open').onclick=$('choose').onclick=()=>$('video-file').click();
$('video-file').onchange=e=>{loadVideo(e.target.files[0]);e.target.value='';};
for(const event of ['dragenter','dragover']) $('stage').addEventListener(event,e=>{e.preventDefault();$('stage').classList.add('dragover');});
$('stage').ondragleave=()=>$('stage').classList.remove('dragover');
$('stage').ondrop=e=>{e.preventDefault();$('stage').classList.remove('dragover');loadVideo(e.dataTransfer.files[0]);};
video.onloadedmetadata=()=>{ if(liveStream){controls();draw();return;} $('duration').textContent=stamp(video.duration); $('seek').max=video.duration; controls(); draw(); };
video.onerror=()=>{status('Il browser non riesce a riprodurre questo video. Prova un MP4 con codec H.264.','error');controls();};
$('play').onclick=()=>{if(video.paused)video.play().catch(e=>status(e.message,'error'));else video.pause();};
video.onplay=()=>{$('play').textContent='Ⅱ';$('play').setAttribute('aria-label','Pausa');};
video.onpause=()=>{$('play').textContent='▶';$('play').setAttribute('aria-label','Riproduci');};
$('back').onclick=()=>{video.pause();video.currentTime=Math.max(0,video.currentTime-.125);};
$('forward').onclick=()=>{video.pause();video.currentTime=Math.min(video.duration,video.currentTime+.125);};
$('seek').oninput=e=>{video.currentTime=+e.target.value;};
$('speed').onchange=e=>{video.playbackRate=+e.target.value;};
$('overlay').onchange=draw;
function nearest(t){
  if(!recording?.frames.length)return null;
  const frames=recording.frames;let lo=0,hi=frames.length;
  while(lo<hi){const mid=(lo+hi)>>1;if(frames[mid].t<t)lo=mid+1;else hi=mid;}
  const a=frames[Math.max(0,lo-1)],b=frames[Math.min(lo,frames.length-1)];
  const result=Math.abs(a.t-t)<=Math.abs(b.t-t)?a:b;
  return Math.abs(result.t-t)<=.3?result:null;
}
function draw(){
  const canvas=$('skeleton'),stage=$('stage');const ratio=video.videoWidth/video.videoHeight;
  if(!Number.isFinite(ratio)){canvas.width=0;return;}
  const width=Math.min(stage.clientWidth,stage.clientHeight*ratio),height=width/ratio;
  canvas.style.width=width+'px';canvas.style.height=height+'px';canvas.width=Math.round(width*devicePixelRatio);canvas.height=Math.round(height*devicePixelRatio);
  const ctx=canvas.getContext('2d');ctx.scale(devicePixelRatio,devicePixelRatio);
  const frame=nearest(video.currentTime),fresh=performance.now()-liveUpdated<1000,points=liveStream?(fresh?livePoints:null):frame?.landmarks;
  if(liveStream&&fresh&&livePicture.width)ctx.drawImage(livePicture,0,0,width,height);
  if(recording){
    const contacts=recording.contacts.filter(c=>c.t0<=video.currentTime&&c.t1>=video.currentTime);
    const hold=recording.holds.some(h=>h.t0<=video.currentTime&&h.t1>=video.currentTime);
    $('frame-state').textContent=points?(hold?'Fermo rilevato':'Posa rilevata'):'Posa non rilevata';
    $('frame-detail').textContent=contacts.length?'Contatti stimati: '+contacts.map(c=>parts[c.part]||c.part).join(', '):points?'Nessun contatto stimato in questo istante.':'Nessun campione utilizzabile in questo istante.';
  }
  if(!liveStream){
    const held=!!recording?.holds.some(h=>h.t0<=video.currentTime&&h.t1>=video.currentTime);
    const angles=[];
    if(points)for(const [a,b,c]of [[11,13,15],[12,14,16],[23,25,27],[24,26,28]]){
      if([a,b,c].some(i=>!points[i]||points[i][2]<.5))continue;
      const u=[(points[a][0]-points[b][0])*width,(points[a][1]-points[b][1])*height],v=[(points[c][0]-points[b][0])*width,(points[c][1]-points[b][1])*height],n=Math.hypot(...u)*Math.hypot(...v);
      if(n>1e-8)angles.push({a,joint:b,c,degrees:Math.round(Math.acos(Math.max(-1,Math.min(1,(u[0]*v[0]+u[1]*v[1])/n)))*180/Math.PI)});
    }
    window.liveEffectPoints=points;
    LiveEffects.update({pole_x:recording?.pole?.x??null,contacts:[],angles,focus_held:held,turn_candidate:false},points,video.currentTime*1000);
  }
  const paintEffects=()=>{if((liveStream&&fresh)||(!liveStream&&recording))LiveEffects.paint(ctx,width,height,!!liveStream&&$('mirror').checked);};
  if(!points||!$('overlay').checked){paintEffects();return;}
  const good=i=>points[i]&&points[i][2]>=.4;
  const referenceFx=$('reference-fx')?.checked;
  const weight=referenceFx?1:Number($('skeleton-size')?.value||1.5),neon=!referenceFx&&$('skeleton-style')?.value!=='clean';
  const scale=Math.max(.85,Math.min(1.8,width/640))*weight;
  ctx.save();ctx.lineCap='round';ctx.lineJoin='round';
  for(const [a,b]of edges){
    if(!good(a)||!good(b))continue;
    const color=referenceFx?'#edf6ed':a%2?'#40edff':'#c4ff45';
    ctx.beginPath();ctx.moveTo(points[a][0]*width,points[a][1]*height);ctx.lineTo(points[b][0]*width,points[b][1]*height);
    ctx.shadowBlur=0;ctx.strokeStyle='#08131d';ctx.lineWidth=(referenceFx?4:7)*scale;ctx.stroke();
    ctx.shadowColor=color;ctx.shadowBlur=neon?10*scale:0;ctx.strokeStyle=color;ctx.lineWidth=(referenceFx?2:3.5)*scale;ctx.stroke();
  }
  for(let i=11;!referenceFx&&i<33;i++){
    if(!good(i))continue;const color=i%2?'#40edff':'#c4ff45';
    ctx.shadowBlur=0;ctx.beginPath();ctx.arc(points[i][0]*width,points[i][1]*height,5*scale,0,Math.PI*2);
    ctx.fillStyle='#08131d';ctx.fill();ctx.strokeStyle=color;ctx.lineWidth=2*scale;
    ctx.shadowColor=color;ctx.shadowBlur=neon?12*scale:0;ctx.stroke();
    ctx.shadowBlur=0;ctx.fillStyle='#ffffff';ctx.beginPath();ctx.arc(points[i][0]*width,points[i][1]*height,1.8*scale,0,Math.PI*2);ctx.fill();
  }
  ctx.restore();paintEffects();
}
function tick(){ $('current').textContent=stamp(video.currentTime);$('seek').value=video.currentTime;draw(); }
video.ontimeupdate=tick; video.onseeked=tick;
if(video.requestVideoFrameCallback){const onFrame=()=>{tick();video.requestVideoFrameCallback(onFrame);};video.requestVideoFrameCallback(onFrame);}
new ResizeObserver(draw).observe($('stage'));
function applyDocument(data){
  if(data.schema_version!=='0.1.0'||!Array.isArray(data.recordings)||data.recordings.length!==1)throw Error('Serve un catalogo 0.1.0 con una sola registrazione.');
  const r=data.recordings[0];
  if(r.landmark_set!=='mediapipe_pose_33'||r.coordinate_system!=='image_xy_visibility'||!Array.isArray(r.frames)||!Array.isArray(r.holds)||!Array.isArray(r.contacts)||!Number.isFinite(r.duration_s)||r.duration_s<=0)throw Error('Formato della registrazione non supportato.');
  if(Math.abs(r.duration_s-video.duration)>Math.max(.5,video.duration*.01))throw Error('La durata dell’analisi non corrisponde al video.');
  let previous=-1;
  for(const f of r.frames){if(!Number.isFinite(f.t)||f.t<=previous||f.t<0||f.t>r.duration_s)throw Error('Timestamp dei frame non validi.');previous=f.t;if(f.landmarks!==null&&(!Array.isArray(f.landmarks)||f.landmarks.length!==33||f.landmarks.some(p=>!Array.isArray(p)||p.length!==3||!p.every(Number.isFinite)||p[2]<0||p[2]>1)))throw Error('Coordinate dei punti non valide.');}
  for(const h of [...r.holds,...r.contacts])if(!Number.isFinite(h.t0)||!Number.isFinite(h.t1)||h.t0<0||h.t1<h.t0||h.t1>r.duration_s)throw Error('Intervalli non validi.');
  documentData=data;recording=r;
  $('badge').textContent='Analisi · bozza';$('coverage').textContent=r.frames.length?Math.round(100*r.frames.filter(f=>f.landmarks).length/r.frames.length)+'%':'0%';
  $('holds-total').textContent=r.holds.length;$('hold-count').textContent=r.holds.length+' momenti';
  $('hold-track').replaceChildren();$('moments').replaceChildren();
  r.holds.forEach((h,i)=>{
    const jump=()=>{video.pause();video.currentTime=h.t0;};
    const marker=document.createElement('button');marker.style.left=(100*h.t0/r.duration_s)+'%';marker.style.width=(100*(h.t1-h.t0)/r.duration_s)+'%';marker.title=`Fermo ${i+1} · ${stamp(h.t0)}`;marker.setAttribute('aria-label',marker.title);marker.onclick=jump;$('hold-track').append(marker);
    const known=data.poses?.find(p=>p.references?.some(ref=>ref.recording_id===r.id&&ref.t>=h.t0&&ref.t<=h.t1));
    const card=document.createElement('article');card.className='moment pose-label-card';
    const jumpButton=document.createElement('button');jumpButton.className='secondary';jumpButton.textContent='Rivedi fermo '+String(i+1).padStart(2,'0');jumpButton.onclick=jump;
    const timing=document.createElement('span');timing.textContent=`${stamp(h.t0)} - ${stamp(h.t1)} | ${(h.t1-h.t0).toFixed(1)} s`;
    const label=document.createElement('label');label.textContent='Nome della posa';label.htmlFor='pose-name-'+i;
    const input=document.createElement('input');input.id=label.htmlFor;input.type='text';input.maxLength=120;input.required=true;input.placeholder='Es. Gemini';input.value=known?.name||'';
    const state=document.createElement('small');state.setAttribute('role','status');state.textContent=known?'Etichettata - bozza da validare':'Posa da nominare';
    const form=document.createElement('form'),save=document.createElement('button');save.type='submit';save.className='primary';save.textContent=known?'Aggiorna nome':'Salva posa';
    form.append(label,input,save);form.onsubmit=async e=>{
      e.preventDefault();const name=input.value.trim();if(!name){input.focus();return;}
      const version=generation;save.disabled=true;state.textContent='Salvataggio...';
      try{
        const response=await fetch('/api/pose-label',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({sha256:r.source.sha256,t0:h.t0,t1:h.t1,name})});
        const item=await response.json();if(!response.ok)throw Error(item.error||'Salvataggio non riuscito');
        if(version!==generation)return;
        const pose={id:item.id,name:item.name,aliases:[],description:'',references:[{recording_id:r.id,t:(h.t0+h.t1)/2}],review:{status:'draft'}};
        documentData.poses=documentData.poses.filter(p=>p.id!==item.id).concat([pose]);
        input.value=item.name;state.textContent='Salvata - bozza da validare';save.textContent='Aggiorna nome';marker.title=item.name+' | '+stamp(h.t0);marker.setAttribute('aria-label',marker.title);
      }catch(error){state.textContent=error.message;}finally{save.disabled=false;}
    };
    if(known){marker.title=known.name+' | '+stamp(h.t0);marker.setAttribute('aria-label',marker.title);}
    card.append(jumpButton,timing,state,form);$('moments').append(card);
  });
  if(!r.holds.length){const empty=document.createElement('div');empty.className='moment-empty';empty.textContent='Nessun fermo rilevato. Puoi comunque esplorare i punti articolari nel player.';$('moments').append(empty);}
  controls();tick();
}
$('analyze').onclick=async()=>{
  if(!file||busy)return;busy=true;controls();status('Caricamento del video nel motore locale…','busy');const version=generation;const analysisStarted=performance.now();
  try{
    const job=await requestStudioAnalysis(file,'analysis');
    status('Analisi in corso. Puoi continuare a guardare il video; su CPU può richiedere qualche minuto.','busy');
    for(;;){await new Promise(resolve=>setTimeout(resolve,1200));if(version!==generation)return;const response=await fetch('/api/jobs/'+job.id);const result=await response.json();if(!response.ok||result.status==='error')throw Error(result.error||'Analisi non disponibile');if(result.status!=='done')status((result.status==='queued'?'In coda':'Analisi su CPU')+' | '+Math.round((performance.now()-analysisStarted)/1000)+' s trascorsi','busy');if(result.status==='done'){applyDocument(result.document);refreshLibrary();status('Analisi completata. Esplora i fermi e rivedi i rilevamenti.');break;}}
  }catch(e){status('Analisi non completata: '+e.message,'error');}finally{busy=false;controls();}
};
$('import-json').onclick=()=>$('json-file').click();
$('json-file').onchange=async e=>{
  const selected=e.target.files[0];e.target.value='';if(!selected)return;
  busy=true;controls();status('Verifica dell’analisi e del video…','busy');
  try{
    const data=JSON.parse(await selected.text());
    if(!sourceHash){const digest=await crypto.subtle.digest('SHA-256',await file.arrayBuffer());sourceHash=Array.from(new Uint8Array(digest),b=>b.toString(16).padStart(2,'0')).join('');}
    if(data.recordings?.[0]?.source?.sha256!==sourceHash)throw Error('Questo JSON appartiene a un altro video. Seleziona il file originale.');
    applyDocument(data);status('Analisi caricata e associata al video originale.');
  }catch(e){status(e.message,'error');}finally{busy=false;controls();}
};
$('export').onclick=()=>{if(!documentData)return;const url=URL.createObjectURL(new Blob([JSON.stringify(documentData,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download=file.name.replace(/\.[^.]+$/,'')+'-analysis.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};

function mirrorLive(){ $('stage').classList.toggle('mirrored',!!liveStream&&$('mirror').checked); }
$('mirror').onchange=mirrorLive;
$('fullscreen').onclick=async()=>{try{const target=$('practice-view');if(document.fullscreenElement)await document.exitFullscreen();else await target.requestFullscreen();}catch(e){status('Schermo intero non disponibile: '+e.message,'error');}};
function stopCamera(message='Webcam fermata.'){
  window.closeStudioPreview?.();
  LiveEffects.stop().catch(LiveEffects.showError);LiveEffects.reset();
  liveEpoch++;livePending=false;
  if(liveStream)liveStream.getTracks().forEach(track=>track.stop());
  liveStream=null;livePoints=null;liveUpdated=0;video.pause();video.srcObject=null;
  document.body.classList.remove('live-mode');$('live-controls').hidden=true;$('stage').classList.remove('mirrored','loaded');$('empty').hidden=false;
  $('badge').textContent='Webcam spenta';$('frame-state').textContent='Webcam spenta';
  $('frame-detail').textContent='Puoi riattivarla o importare un video.';
  controls();draw();status(message);
}
$('stop-camera').onclick=()=>stopCamera();
window.addEventListener('pagehide',()=>{liveEpoch++;if(liveStream)liveStream.getTracks().forEach(t=>t.stop());});
$('camera').onclick=async()=>{
  if(busy||livePending||liveStream)return;
  const epoch=++liveEpoch;livePending=true;controls();status('Consenti l?accesso alla fotocamera nel browser.','busy');
  $('live-controls').hidden=false;
  try{
    if(!navigator.mediaDevices?.getUserMedia)throw Error('Apri lo studio su http://127.0.0.1:8765 per usare la fotocamera.');
    const stream=await navigator.mediaDevices.getUserMedia({video:{width:{ideal:1280},height:{ideal:720},frameRate:{ideal:30}},audio:false});
    if(epoch!==liveEpoch){stream.getTracks().forEach(t=>t.stop());return;}
    liveSession=crypto.randomUUID();LiveEffects.reset();liveStream=stream;livePending=false;file=null;recording=null;documentData=null;
    if(objectUrl){URL.revokeObjectURL(objectUrl);objectUrl=null;}
    video.removeAttribute('src');video.srcObject=stream;video.muted=true;video.playbackRate=1;
    // Reveal the preview before awaiting playback or initializing inference.
    document.body.classList.add('live-mode');$('stage').classList.add('loaded');$('empty').hidden=true;mirrorLive();
    await video.play();if(epoch!==liveEpoch)return;
    stream.getVideoTracks()[0].addEventListener('ended',()=>{if(epoch===liveEpoch)stopCamera('Fotocamera disconnessa.');});
    document.body.classList.add('live-mode');$('stage').classList.add('loaded');$('empty').hidden=true;mirrorLive();
    $('session-name').textContent='Lezione dal vivo';$('session-meta').textContent='Webcam locale ? microfono spento ? nessuna registrazione';
    $('badge').textContent='LIVE';$('coverage').textContent='?';$('holds-total').textContent='?';
    $('hold-track').replaceChildren();$('hold-count').textContent='Modalit? live';$('moments').replaceChildren();
    $('frame-state').textContent='Inizializzazione del rilevatore';$('frame-detail').textContent='Inquadra una persona a figura intera.';
    status('Webcam attiva. Preparazione del modello locale?','busy');controls();
    const capture=document.createElement('canvas');
    while(epoch===liveEpoch&&liveStream){
      if(document.hidden&&!window.studioPreviewActive){await new Promise(r=>setTimeout(r,250));continue;}
      const start=performance.now();
      capture.width=Math.min(640,video.videoWidth);capture.height=Math.round(capture.width*video.videoHeight/video.videoWidth);
      capture.getContext('2d').drawImage(video,0,0,capture.width,capture.height);
      const blob=await new Promise(resolve=>capture.toBlob(resolve,'image/jpeg',.8));
      if(epoch!==liveEpoch)break;if(!blob)throw Error('Cattura del fotogramma non riuscita.');
      const response=await fetch('/api/live',{method:'POST',headers:{'Content-Type':'image/jpeg','X-Live-Session':liveSession,...($('manual-pole').checked?{'X-Pole-X':$('pole-position').value}:{})},body:blob,signal:AbortSignal.timeout(60000)});
      if(epoch!==liveEpoch)break;
      if(response.status===429){await new Promise(r=>setTimeout(r,150));continue;}
      const result=await response.json();if(epoch!==liveEpoch)break;if(!response.ok)throw Error(result.error||'Errore del motore locale');
      livePicture.width=capture.width;livePicture.height=capture.height;livePicture.getContext('2d').drawImage(capture,0,0);
      window.liveEffectPoints=result.landmarks;LiveEffects.update(result.metrics,result.landmarks,start);
      livePoints=result.landmarks;liveUpdated=performance.now();const elapsed=liveUpdated-start;
      $('live-info').textContent=`LIVE ? ${(1000/Math.max(elapsed,100)).toFixed(1)} analisi/s ? ritardo ${Math.round(elapsed)} ms`;
      $('frame-state').textContent=livePoints?'Posa rilevata':'Persona non rilevata';
      $('frame-detail').textContent=livePoints?'Immagine e scheletro sincronizzati. Sinistra e destra sono anatomiche.':'Allontanati dalla webcam e inquadra tutto il corpo con buona illuminazione.';
      status('Analisi dal vivo attiva. Usa lo schermo intero per la lezione.');draw();
      await new Promise(r=>setTimeout(r,Math.max(0,100-(performance.now()-start))));
    }
  }catch(e){if(epoch===liveEpoch){stopCamera();status(e.name==='NotAllowedError'?'Accesso alla webcam negato. Abilita la fotocamera nelle impostazioni del browser e riprova.':e.name==='NotFoundError'?'Nessuna fotocamera trovata. Collega una webcam e riprova.':'Webcam interrotta: '+e.message,'error');}}
};

$("record-live").onclick=()=>{if(liveStream)LiveEffects.start(liveStream,$("skeleton")).catch(LiveEffects.showError);};

// Reference playback stays independent of webcam capture and recording.
const referenceVideo=$('reference-video');
let referenceUrl=null, referenceFile=null;
$('reference-choose').onclick=()=>$('reference-file').click();
$('reference-file').onchange=e=>{
  const selected=e.target.files[0]; e.target.value=''; if(!selected)return;
  referenceFile=selected;
  referenceVideo.pause(); referenceVideo.removeAttribute('src'); referenceVideo.load();
  if(referenceUrl)URL.revokeObjectURL(referenceUrl);
  referenceUrl=URL.createObjectURL(selected); referenceVideo.src=referenceUrl;
  referenceVideo.hidden=false; $('reference-empty').hidden=true;
  $('reference-status').textContent=selected.name;
};
referenceVideo.addEventListener('loadedmetadata',()=>{referenceVideo.playbackRate=+$('reference-speed').value;});
referenceVideo.addEventListener('error',()=>{$('reference-status').textContent='Video guida non riproducibile. Prova un MP4 H.264.';});
$('reference-speed').onchange=e=>{referenceVideo.playbackRate=+e.target.value;};
$('reference-loop').onchange=e=>{referenceVideo.loop=e.target.checked;};
$('reference-mirror').onchange=e=>{referenceVideo.classList.toggle('mirrored',e.target.checked);};
window.addEventListener('pagehide',()=>{referenceVideo.pause();});

// Workspace appearance and independent camera preview. Never move the live DOM.
(() => {
  const themeButton=$('theme-toggle');
  let saved=null;try{saved=localStorage.getItem('pole-motion-theme');}catch{}
  function theme(dark){
    document.documentElement.dataset.theme=dark?'dark':'light';
    themeButton.textContent=dark?'Tema chiaro':'Tema scuro';
    themeButton.setAttribute('aria-pressed',String(dark));
  }
  theme(saved?saved==='dark':window.matchMedia('(prefers-color-scheme: dark)').matches);
  themeButton.onclick=()=>{const dark=document.documentElement.dataset.theme!=='dark';theme(dark);try{localStorage.setItem('pole-motion-theme',dark?'dark':'light');}catch{}};
  $('preview-enlarge').onclick=()=>{
    const enlarged=document.body.classList.toggle('preview-enlarged');
    $('preview-enlarge').textContent=enlarged?'Ripristina confronto':'Ingrandisci anteprima';
    $('preview-enlarge').setAttribute('aria-pressed',String(enlarged));draw();
  };
  $('preview-fullscreen').onclick=async()=>{try{
    if(document.fullscreenElement)await document.exitFullscreen();
    else await $('camera-view').requestFullscreen();
  }catch(e){status('Usa Ingrandisci anteprima: schermo intero non disponibile.','error');}};
  let floating=null,opening=false;
  window.studioPreviewActive=false;
  function closePreview(){
    const previous=floating;floating=null;window.studioPreviewActive=false;
    $('preview-detach').textContent='Stacca webcam';
    if(previous&&!previous.closed)previous.close();
  }
  window.closeStudioPreview=closePreview;
  $('preview-detach').onclick=async()=>{
    if(floating&&!floating.closed){closePreview();return;}
    if(opening)return;
    if(!liveStream){status("Avvia la webcam prima di staccare l'anteprima.");return;}
    opening=true;
    try{
      const popup=window.documentPictureInPicture?.requestWindow
        ?await window.documentPictureInPicture.requestWindow({width:800,height:540})
        :window.open('about:blank','pole-motion-preview','popup=yes,width=800,height=540,resizable=yes');
      if(!popup)throw Error('Consenti la finestra popup per questo Studio oppure usa Ingrandisci anteprima.');
      if(!liveStream){popup.close();return;}
      floating=popup;window.studioPreviewActive=true;
      popup.document.title='Pole Motion - Webcam';
      const style=popup.document.createElement('style');
      style.textContent='body{margin:0;background:#101b18;color:#e5eee8;font:14px system-ui;display:flex;flex-direction:column;height:100vh}header{display:flex;align-items:center;justify-content:space-between;padding:12px;gap:12px}button{background:#254f40;color:white;border:1px solid #547765;padding:8px 12px;border-radius:6px;cursor:pointer}canvas{display:block;flex:1;min-height:0;width:100%;object-fit:contain}';
      const header=popup.document.createElement('header'),label=popup.document.createElement('span'),back=popup.document.createElement('button'),stop=popup.document.createElement('button');
      label.textContent='Webcam con effetti';back.textContent='Riporta nello Studio';back.onclick=closePreview;
      stop.textContent='Ferma webcam';stop.onclick=()=>stopCamera();header.append(label,back,stop);
      const preview=popup.document.createElement('canvas');preview.width=1280;preview.height=720;
      popup.document.head.append(style);popup.document.body.replaceChildren(header,preview);
      $('preview-detach').textContent='Riporta nello Studio';
      popup.addEventListener('pagehide',()=>{if(floating===popup){floating=null;window.studioPreviewActive=false;$('preview-detach').textContent='Stacca webcam';}},{once:true});
      const copy=()=>{
        if(popup.closed||floating!==popup||!liveStream){if(floating===popup)closePreview();return;}
        draw();const c=preview.getContext('2d'),original=$('skeleton');
        c.fillStyle='#101b18';c.fillRect(0,0,1280,720);
        const fresh=performance.now()-liveUpdated<1000;
        if(fresh&&original.width&&original.height){
          const scale=Math.min(1280/original.width,720/original.height),w=original.width*scale,h=original.height*scale;
          c.save();if($('mirror').checked){c.translate(1280,0);c.scale(-1,1);}c.drawImage(original,(1280-w)/2,(720-h)/2,w,h);c.restore();
        }else{c.fillStyle='#dbe8df';c.font='24px sans-serif';c.textAlign='center';c.fillText('In attesa del tracciamento...',640,360);}
        label.textContent=$('live-info').textContent;
        popup.requestAnimationFrame(copy);
      };popup.requestAnimationFrame(copy);
    }catch(e){closePreview();status(e.message,'error');}finally{opening=false;}
  };
  window.addEventListener('pagehide',closePreview);
})();

// One effects panel, accessible from the preview even in fullscreen.
(() => {
  const dialog=$('effects-dialog'),settings=$('effects-settings');
  $('effects-body').append(settings);settings.open=true;
  $('effects-open').onclick=()=>{if(!dialog.open)dialog.showModal();};
  $('effects-close').onclick=()=>dialog.close();
  dialog.addEventListener('click',e=>{if(e.target===dialog){const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)dialog.close();}});
  for(const id of ['skeleton-style','skeleton-size']){
    try{const stored=localStorage.getItem('pole-motion-'+id);if(stored!==null&&((id==='skeleton-style'&&['game','clean'].includes(stored))||(id==='skeleton-size'&&Number(stored)>=.8&&Number(stored)<=2.4)))$(id).value=stored;}catch{}
    $(id).addEventListener('input',()=>{
      $('skeleton-size-value').value=Number($('skeleton-size').value).toFixed(1)+'x';
      try{localStorage.setItem('pole-motion-'+id,$(id).value);}catch{}draw();
    });
  }
  $('skeleton-size-value').value=Number($('skeleton-size').value).toFixed(1)+'x';
})();

// Persistent library: direct media streaming and automatic content-hash matching.
let libraryVideos=[];
const libraryHashes=new WeakMap();
async function refreshLibrary(){
  try{const r=await fetch('/api/library');if(!r.ok)throw Error("Riavvia lo Studio per attivare l'archivio.");
    const data=await r.json();libraryVideos=data.videos;$('engine-info').textContent='Motore: '+data.engine+' | Riutilizzo automatico delle analisi';renderLibrary();
  }catch(e){$('library-list').textContent=e.message;}
}
function renderLibrary(){
  const list=$('library-list');list.replaceChildren();const search=$('library-search').value.toLowerCase();
  const shown=libraryVideos.filter(v=>(v.name+' '+new Date(v.created*1000).toLocaleString()).toLowerCase().includes(search));
  if(!shown.length){list.textContent=libraryVideos.length?'Nessun risultato.':'Le analisi completate appariranno qui automaticamente.';return;}
  for(const item of shown){
    const card=document.createElement('article');card.className='library-item';
    const title=document.createElement('strong');title.textContent=item.name;
    const meta=document.createElement('small');meta.textContent=new Date(item.created*1000).toLocaleString()+' | '+(item.size/1024**2).toFixed(1)+' MB | '+Object.keys(item.results).map(k=>k==='avatar'?'Avatar 3D':'Analisi 2D').join(' + ');
    const open=document.createElement('button');open.className='secondary';open.textContent='Riprendi';open.onclick=()=>{
      if(busy||liveStream||livePending){status("Ferma la webcam o attendi la fine dell'analisi prima di aprire un video.");return;}
      loadVideo({name:item.name,size:item.size,archiveId:item.video_id,sha256:item.sha256});
    };card.append(title,meta,open);list.append(card);
  }
}
async function savedGroup(selected){
  if(!libraryVideos.length)await refreshLibrary();
  if(!libraryVideos.length)return null;
  if(selected.sha256)return libraryVideos.find(v=>v.sha256===selected.sha256)||null;
  if(!libraryVideos.some(v=>v.size===selected.size))return null;
  if(!libraryHashes.has(selected))libraryHashes.set(selected,selected.arrayBuffer().then(bytes=>crypto.subtle.digest('SHA-256',bytes)).then(digest=>Array.from(new Uint8Array(digest),b=>b.toString(16).padStart(2,'0')).join('')));
  const hash=await libraryHashes.get(selected);
  return libraryVideos.find(v=>v.sha256===hash)||null;
}
async function restoreSavedAnalysis(selected,version){
  try{
    const group=await savedGroup(selected);if(!group||version!==generation)return;
    const results=await Promise.all(['analysis','avatar'].map(async kind=>{const entry=group.results[kind];if(!entry)return null;const r=await fetch('/api/library/'+entry.id+'/document');if(!r.ok)throw Error('Risultato salvato non disponibile');return r.json();}));
    if(version!==generation)return;
    if(video.readyState<1)await new Promise((resolve,reject)=>{const loaded=()=>{cleanup();resolve();},failed=()=>{cleanup();reject(Error('Video archiviato non riproducibile'));};const cleanup=()=>{video.removeEventListener('loadedmetadata',loaded);video.removeEventListener('error',failed);};video.addEventListener('loadedmetadata',loaded,{once:true});video.addEventListener('error',failed,{once:true});});
    if(version!==generation)return;sourceHash=group.sha256;
    if(results[0])applyDocument(results[0]);
    if(results[1])window.restoreAvatarMotion?.(results[1],selected,video,results[0]?.recordings?.[0]);
    status('Analisi recuperate automaticamente. Nessun ricalcolo.');
  }catch(e){if(version===generation)status('Recupero analisi: '+e.message,'error');}
}
async function requestStudioAnalysis(selected,kind){
  const group=await savedGroup(selected),entry=group?.results[kind];
  if(entry)return {id:entry.id,cached:true};
  const headers={'Content-Type':'application/octet-stream','X-Video-Name':encodeURIComponent(selected.name)};
  if(selected.archiveId)headers['X-Archive-ID']=selected.archiveId;
  const r=await fetch(kind==='avatar'?'/api/avatar':'/api/analyze',{method:'POST',headers,body:selected.archiveId?'reuse':selected});
  const result=await r.json();if(!r.ok)throw Error(result.error||'Analisi non disponibile');return result;
}
$('library-refresh').onclick=refreshLibrary;$('library-search').oninput=renderLibrary;
refreshLibrary();
