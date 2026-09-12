/* Live presentation and recording. Measurements remain in original image coordinates. */
window.LiveEffects = (() => {
  let metrics=null, flashUntil=0, recorders=[], samples=[], started=0, recording=false, finishing=false, timer=null;
  let frameStream=null;
  let effectPoints=null, pulses=[], lastCapture=null, anchor=null, stillSince=0, focus=null, previousGrip={}, wasInverted=false, previousExtended={};
  const extremities={left_hand:[15,19,21],right_hand:[16,20,22],left_foot:[27,29,31],right_foot:[28,30,32]};
  function center(points,indices){const good=indices.map(i=>points?.[i]).filter(p=>p&&p[2]>=.3);return good.length?[good.reduce((s,p)=>s+p[0],0)/good.length,good.reduce((s,p)=>s+p[1],0)/good.length]:null;}
  function pulse(xy,color){pulses.push({xy,color,start:performance.now()});pulses=pulses.slice(-12);}
  function trackEffects(value,points,t){
    effectPoints=points;
    if(lastCapture===t)return;
    if(lastCapture!==null&&(t<lastCapture||t-lastCapture>700)){anchor=null;focus=null;pulses=[];previousGrip={};wasInverted=false;previousExtended={};}
    lastCapture=t;
    if(!points){anchor=null;focus=null;previousGrip={};wasInverted=false;previousExtended={};pulses=[];return;}
    const torso=[11,12,23,24].map(i=>points[i]);
    const visible=points.slice(11).filter(p=>p&&p[2]>=.3);
    if(torso.every(p=>p&&p[2]>=.4)&&visible.length>=4){
      const xy=torso.map(p=>p.slice(0,2));
      if(!anchor||Math.max(...xy.map((p,i)=>Math.hypot(p[0]-anchor[i][0],p[1]-anchor[i][1])))>.025){anchor=xy;stillSince=t;}
      const locked=value?.focus_held??(t-stillSince>=600);
      const box=[Math.max(.02,Math.min(...visible.map(p=>p[0]))-.03),Math.max(.02,Math.min(...visible.map(p=>p[1]))-.03),Math.min(.98,Math.max(...visible.map(p=>p[0]))+.03),Math.min(.98,Math.max(...visible.map(p=>p[1]))+.03)];
      if(locked&&!focus?.locked)pulse([(box[0]+box[2])/2,(box[1]+box[3])/2],'#72ff54');
      focus={box,locked};
      const inverted=(torso[0][1]+torso[1][1])/2>(torso[2][1]+torso[3][1])/2+.05;
      if(inverted&&!wasInverted)pulse(center(points,[11,12]),'#d48cff');wasInverted=inverted;
    }else{anchor=null;focus=null;wasInverted=false;}
    for(const [part,ids]of Object.entries(extremities)){
      const xy=center(points,ids),on=!!xy&&Number.isFinite(value?.pole_x)&&Math.abs(xy[0]-value.pole_x)<.09;
      if(on&&!previousGrip[part])pulse(xy,'#72ff54');previousGrip[part]=on;
    }
    for(const angle of value?.angles||[]){const extended=angle.degrees>=165;if(extended&&!previousExtended[angle.joint])pulse(points[angle.joint].slice(0,2),'#45e7ff');previousExtended[angle.joint]=extended;}
  }
  const el=id=>document.getElementById(id);
  function update(value, points, capturedAt){
    metrics=value;trackEffects(value,points,capturedAt);
    if(value?.turn_candidate)flashUntil=performance.now()+1400;
    if(recording&&capturedAt>=started)samples.push({t:(capturedAt-started)/1000,landmarks:points,metrics:value});
  }
  function paint(ctx,w,h,mirror){
    if(!metrics)return;
    const photo=el('reference-fx')?.checked?null:metrics.photo;
    if(photo?.box){
      const [x0,y0,x1,y1]=photo.box;
      const pad=12, x=Math.max(8,x0*w-pad),y=Math.max(8,y0*h-pad);
      const right=Math.min(w-8,x1*w+pad),bottom=Math.min(h-8,y1*h+pad);
      const bw=right-x,bh=bottom-y;
      if(el('show-hold')?.checked&&photo.held){
        ctx.save();ctx.strokeStyle='#8effba';ctx.shadowColor='#8effba';ctx.shadowBlur=18;ctx.lineWidth=3;
        ctx.globalAlpha=.65;ctx.beginPath();ctx.ellipse((x+right)/2,(y+bottom)/2,bw/2,bh/2,0,0,Math.PI*2);ctx.stroke();ctx.restore();
      }
      if(el('show-photo')?.checked){
        ctx.save();ctx.strokeStyle=photo.ready?'#8effba':'#f6cf71';ctx.lineWidth=3;
        const corner=Math.min(24,bw/4,bh/4);
        for(const [cx,cy,dx,dy] of [[x,y,1,1],[right,y,-1,1],[x,bottom,1,-1],[right,bottom,-1,-1]]){
          ctx.beginPath();ctx.moveTo(cx+dx*corner,cy);ctx.lineTo(cx,cy);ctx.lineTo(cx,cy+dy*corner);ctx.stroke();
        }
        ctx.translate((x+right)/2,Math.min(h-20,Math.max(24,y-8)));if(mirror)ctx.scale(-1,1);
        const label=photo.ready?'Pronta per lo scatto':photo.held?'Posa mantenuta':'Mantieni la posa';
        ctx.font='bold 13px sans-serif';ctx.textAlign='center';const tw=ctx.measureText(label).width;
        ctx.fillStyle='#13271d';ctx.fillRect(-tw/2-8,-16,tw+16,22);ctx.fillStyle=photo.ready?'#8effba':'#f6cf71';ctx.fillText(label,0,0);ctx.restore();
      }
    }
    if(!el('reference-fx')?.checked&&el('show-pole').checked&&metrics.pole_x!==null){
      ctx.save();ctx.strokeStyle='#f6cf71';ctx.lineWidth=2;ctx.setLineDash([8,5]);ctx.beginPath();ctx.moveTo(metrics.pole_x*w,0);ctx.lineTo(metrics.pole_x*w,h);ctx.stroke();ctx.restore();
    }
    if(!el('reference-fx')?.checked&&el('show-grips').checked)for(const contact of metrics.contacts){
      ctx.save();ctx.shadowColor='#8effba';ctx.shadowBlur=22;ctx.strokeStyle='#8effba';ctx.lineWidth=4;ctx.beginPath();ctx.arc(contact.xy[0]*w,contact.xy[1]*h,15+3*Math.sin(performance.now()/140),0,Math.PI*2);ctx.stroke();ctx.restore();
    }
    if(el('show-angles').checked&&window.liveEffectPoints)for(const angle of metrics.angles){
      const p=window.liveEffectPoints[angle.joint],a=window.liveEffectPoints[angle.a],b=window.liveEffectPoints[angle.c];
      if(!p)continue;
      const start=Math.atan2((a[1]-p[1])*h,(a[0]-p[0])*w),end=Math.atan2((b[1]-p[1])*h,(b[0]-p[0])*w);
      let delta=(end-start+Math.PI*3)%(Math.PI*2)-Math.PI;
      ctx.save();ctx.strokeStyle='#ffc978';ctx.lineWidth=2;ctx.beginPath();ctx.arc(p[0]*w,p[1]*h,20,start,start+delta,delta<0);ctx.stroke();
      ctx.translate(p[0]*w+12,p[1]*h-12);if(mirror)ctx.scale(-1,1);
      ctx.font='bold 14px sans-serif';ctx.fillStyle='#13271d';ctx.fillRect(-3,-15,48,20);ctx.fillStyle='#ffe4ab';ctx.fillText(angle.degrees+'°',0,0);ctx.restore();
    }
    if(el('reference-fx')?.checked&&effectPoints){
      const scale=Math.max(.7,Math.min(1.8,w/960));
      function strokeLine(x0,y0,x1,y1,color,size){ctx.beginPath();ctx.moveTo(x0,y0);ctx.lineTo(x1,y1);ctx.strokeStyle='#08110d';ctx.lineWidth=(size+2)*scale;ctx.stroke();ctx.strokeStyle=color;ctx.lineWidth=size*scale;ctx.stroke();}
      function text(label,x,y,color){ctx.save();ctx.translate(x,y);if(mirror)ctx.scale(-1,1);ctx.font=`bold ${Math.max(12,15*scale)}px sans-serif`;ctx.lineWidth=3;ctx.strokeStyle='#08110d';ctx.strokeText(label,0,0);ctx.fillStyle=color;ctx.fillText(label,0,0);ctx.restore();}
      ctx.save();ctx.shadowBlur=0;
      if(el('show-pole').checked&&Number.isFinite(metrics.pole_x)){strokeLine(metrics.pole_x*w,16,metrics.pole_x*w,h-16,'#ffbd24',4);text('PALO',metrics.pole_x*w+8,h/2,'#ffbd24');}
      if(el('show-grips').checked)for(const [part,ids]of Object.entries(extremities)){
        const xy=center(effectPoints,ids);if(!xy)continue;const on=previousGrip[part],r=10*scale;
        ctx.beginPath();ctx.arc(xy[0]*w,xy[1]*h,r,0,Math.PI*2);ctx.lineWidth=6*scale;ctx.strokeStyle='#08110d';ctx.stroke();
        ctx.strokeStyle=on?'#72ff54':'#ffd34b';ctx.fillStyle='#72ff54';ctx.lineWidth=3*scale;if(on)ctx.fill();ctx.stroke();
      }
      if(el('show-photo').checked&&focus){
        const [x0,y0,x1,y1]=focus.box,x=x0*w,y=y0*h,right=x1*w,bottom=y1*h,len=Math.min(30*scale,(right-x)/4,(bottom-y)/4),color=focus.locked?'#72ff54':'#ffd34b';
        for(const [cx,cy,dx,dy]of [[x,y,1,1],[right,y,-1,1],[x,bottom,1,-1],[right,bottom,-1,-1]]){strokeLine(cx,cy,cx+dx*len,cy,color,4);strokeLine(cx,cy,cx,cy+dy*len,color,4);}
        if(focus.locked){ctx.strokeStyle=color;ctx.lineWidth=scale;ctx.strokeRect(x,y,right-x,bottom-y);}
        text(focus.locked?'AF LOCK - POSA STABILE':'AF-C - INSEGUIMENTO',18,28,color);
      }
      if(el('show-bursts')?.checked){
        const now=performance.now();pulses=pulses.filter(p=>now-p.start<750);
        for(const p of pulses){const age=(now-p.start)/750;ctx.globalAlpha=1-age;ctx.beginPath();ctx.arc(p.xy[0]*w,p.xy[1]*h,(14+age*85)*scale,0,Math.PI*2);ctx.lineWidth=6*scale;ctx.strokeStyle='#08110d';ctx.stroke();ctx.lineWidth=3*scale;ctx.strokeStyle=p.color;ctx.stroke();}ctx.globalAlpha=1;
      }
      ctx.restore();
    }
    if(el('show-turns').checked&&performance.now()<flashUntil){
      ctx.save();ctx.strokeStyle='#caa6ff';ctx.lineWidth=8;ctx.strokeRect(8,8,w-16,h-16);ctx.translate(w/2,35);if(mirror)ctx.scale(-1,1);ctx.textAlign='center';ctx.fillStyle='#eadcff';ctx.font='bold 19px sans-serif';ctx.fillText('Possibile giravolta · sperimentale',0,0);ctx.restore();
    }
  }
  function reset(){effectPoints=null;pulses=[];lastCapture=null;anchor=null;focus=null;previousGrip={};wasInverted=false;previousExtended={};metrics=null;flashUntil=0;window.liveEffectPoints=null;}
  function download(blob,name,label){
    const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=name;a.textContent=label;a.className='secondary';el('record-downloads').append(a);
  }
  async function stop(){
    if(!recording||finishing)return;
    recording=false;finishing=true;clearTimeout(timer);el('record-live').disabled=true;el('record-state').textContent='Preparazione dei file…';
    const duration=(performance.now()-started)/1000;
    const results=await Promise.all(recorders.map(item=>new Promise(resolve=>{item.rec.addEventListener('stop',()=>resolve({...item,blob:new Blob(item.chunks,{type:item.rec.mimeType})}),{once:true});item.rec.stop();})));
    if(frameStream){frameStream.getTracks().forEach(t=>t.stop());frameStream=null;}
    const name='pole-session-'+new Date().toISOString().replace(/[:.]/g,'-');
    for(const item of results)download(item.blob,name+'-'+item.kind+(item.blob.type.includes('mp4')?'.mp4':'.webm'),item.kind==='original'?'Scarica originale':'Scarica video con effetti');
    const original=results.find(r=>r.kind==='original');
    const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',await original.blob.arrayBuffer())),b=>b.toString(16).padStart(2,'0')).join('');
    const data={format:'pole-motion-live-0.1',source_sha256:hash,duration_s:duration,coordinate_system:'image_xy_visibility',landmark_set:'mediapipe_pose_33',timing:'Seconds from original MediaRecorder start event; browser capture timing is approximate.',recordings:results.map(r=>({kind:r.kind,start_offset_s:r.offset})),samples};
    download(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}),name+'.json','Scarica misure JSON');
    finishing=false;el('record-live').disabled=false;el('record-live').textContent='Registra';el('record-state').textContent='File pronti: scaricali prima di chiudere la pagina.';
  }
  async function start(stream,canvas){
    if(finishing)return;
    if(recording){await stop();return;}
    if(!window.MediaRecorder)throw Error('Registrazione non supportata da questo browser.');
    const mime=['video/webm;codecs=vp8','video/webm','video/mp4'].find(t=>MediaRecorder.isTypeSupported(t));
    if(!mime)throw Error('Nessun formato video supportato per la registrazione.');
    el('record-live').disabled=true;
    recorders=[];samples=[];
    const add=(source,kind)=>{const chunks=[],rec=new MediaRecorder(source,{mimeType:mime});const item={rec,chunks,kind,offset:0};rec.ondataavailable=e=>{if(e.data.size)chunks.push(e.data);};recorders.push(item);return item;};
    const original=add(stream,'original');
    if(el('record-effects').checked){
      // A fixed-size canvas avoids resizing the recording when the UI enters fullscreen.
      const fixed=document.createElement('canvas');fixed.width=1280;fixed.height=720;
      frameStream=fixed.captureStream(30);add(frameStream,'effects');
      const copy=()=>{if(!recording)return;const c=fixed.getContext('2d');c.fillStyle='#141f1b';c.fillRect(0,0,1280,720);const scale=Math.min(1280/canvas.width,720/canvas.height),w=canvas.width*scale,h=canvas.height*scale;if(w&&h){c.save();if(el('mirror').checked){c.translate(1280,0);c.scale(-1,1);}c.drawImage(canvas,(1280-w)/2,(720-h)/2,w,h);c.restore();}requestAnimationFrame(copy);};
      original.rec.addEventListener('start',()=>requestAnimationFrame(copy),{once:true});
    }
    original.rec.addEventListener('start',()=>{started=performance.now();recording=true;el('record-live').textContent='Ferma registrazione';el('record-state').textContent='REC · massimo 5 minuti · audio spento';timer=setTimeout(()=>stop().catch(showError),300000);for(const item of recorders.slice(1)){item.rec.addEventListener('start',()=>{item.offset=(performance.now()-started)/1000;},{once:true});item.rec.start(1000);}}, {once:true});
    original.rec.addEventListener('start',()=>{el('record-live').disabled=false;},{once:true});
    original.rec.start(1000);
  }
  function showError(e){el('record-state').textContent='Errore registrazione: '+e.message;}
  window.addEventListener('beforeunload',e=>{if(recording||finishing){e.preventDefault();e.returnValue='';}});
  return {update,paint,reset,start,stop,showError,isRecording:()=>recording||finishing};
})();
