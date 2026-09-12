// Browser-independent lifecycle test: start, capture timestamps, stop, downloadable artifacts.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const {webcrypto}=require('node:crypto');
test('recording produces original, effects and hash-associated measurements',async()=>{
  let time=1000;const downloads=[],blobs=[];const nodes=new Map();
  const node=id=>{if(!nodes.has(id))nodes.set(id,{checked:true,append:a=>downloads.push(a)});return nodes.get(id);};
  const media=[];
  class Recorder extends EventTarget{
    static isTypeSupported(){return true;}
    constructor(stream,options){super();this.mimeType=options.mimeType;media.push(this);}
    start(){queueMicrotask(()=>this.dispatchEvent(new Event('start')));}
    stop(){this.ondataavailable({data:new Blob(['video'])});queueMicrotask(()=>this.dispatchEvent(new Event('stop')));}
  }
  let effectsStopped=false;
  const context={window:{addEventListener(){}},document:{getElementById:node,createElement:tag=>tag==='a'?{}:{captureStream:()=>({getTracks:()=>[{stop(){effectsStopped=true;}}]})}},
    MediaRecorder:Recorder,performance:{now:()=>time},Blob,crypto:webcrypto,URL:{createObjectURL:blob=>{blobs.push(blob);return 'blob:'+blobs.length;}},
    setTimeout:()=>1,clearTimeout(){},requestAnimationFrame(){},Uint8Array};
  context.window.MediaRecorder=Recorder;
  vm.createContext(context);vm.runInContext(fs.readFileSync('pole_motion/studio_web/live-effects.js','utf8'),context);
  const effects=context.window.LiveEffects;
  await effects.start({},{});await Promise.resolve();
  assert.equal(media.length,2);
  effects.update({contacts:[]},null,900); // sample captured before recording must be excluded
  effects.update({contacts:[]},null,1250);
  time=2000;await effects.stop();
  assert.equal(downloads.length,3);assert.ok(effectsStopped);
  const data=JSON.parse(await blobs[2].text());
  assert.equal(data.samples.length,1);assert.equal(data.samples[0].t,.25);
  assert.equal(data.duration_s,1);assert.equal(data.source_sha256.length,64);
  assert.equal(data.recordings[0].kind,'original');assert.equal(effects.isRecording(),false);
});


test('reference FX show free amber circles, green proximity and focus lock, then clear missing pose',()=>{
  let time=1000;const strokes=[],labels=[];
  const ctx={save(){},restore(){},beginPath(){},moveTo(){},lineTo(){},arc(){},fill(){},stroke(){strokes.push(this.strokeStyle);},strokeRect(){},translate(){},scale(){},strokeText(){},fillText(t){labels.push(t);}};
  const context={window:{addEventListener(){}},document:{getElementById:id=>({checked:['reference-fx','show-grips','show-photo','show-bursts'].includes(id)})},performance:{now:()=>time}};
  vm.createContext(context);vm.runInContext(fs.readFileSync('pole_motion/studio_web/live-effects.js','utf8'),context);
  const effects=context.window.LiveEffects;
  const p=Array.from({length:33},()=>[.8,.5,1]);p[11]=[.4,.3,1];p[12]=[.6,.3,1];p[23]=[.4,.6,1];p[24]=[.6,.6,1];
  effects.update({pole_x:.5,angles:[],contacts:[]},p,0);effects.paint(ctx,960,540,false);
  assert.ok(strokes.includes('#ffd34b'));assert.ok(labels.includes('AF-C - INSEGUIMENTO'));
  for(const i of [15,19,21])p[i]=[.5,.4,1];
  effects.update({pole_x:.5,angles:[],contacts:[]},p,500);
  time=1601;effects.update({pole_x:.5,angles:[],contacts:[]},p,601);effects.paint(ctx,960,540,false);
  assert.ok(strokes.includes('#72ff54'));assert.ok(labels.includes('AF LOCK - POSA STABILE'));
  labels.length=0;strokes.length=0;
  effects.update({pole_x:.5,angles:[],contacts:[]},null,700);effects.paint(ctx,960,540,false);
  assert.equal(labels.length,0);assert.equal(strokes.length,0);
});
