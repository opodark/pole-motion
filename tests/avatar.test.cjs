const {test}=require('node:test');const assert=require('node:assert/strict');
const {sample,sampleRoot}=require('../pole_motion/studio_web/avatar.js');
test('interpolates depth but never bridges missing detections or long gaps',()=>{
assert.deepEqual(sample([{t:0,points:[[0,0,0,1]]},{t:.1,points:[[2,4,6,.7]]}],.05),[[1,2,3,.7]]);
assert.equal(sample([{t:0,points:[[0,0,0,1]]},{t:.1,points:null}],.1),null);
assert.equal(sample([{t:0,points:[[0,0,0,1]]},{t:2,points:[[2,4,6,1]]}],1),null);
});
test('interpolates the hip trajectory used to move the complete rig',()=>{
const root=sampleRoot([{t:0,root:[.4,.8,1]},{t:.1,root:[.6,.4,.8]}],.05);
assert.ok(Math.abs(root[0]-.5)<1e-9);assert.ok(Math.abs(root[1]-.6)<1e-9);assert.equal(root[2],.8);
});
