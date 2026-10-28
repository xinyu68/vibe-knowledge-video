// Domain checks for the illustrative model; these are not experimental results.
'use strict';
const fs=require('fs'),path=require('path');
global.window={};require('./traffic.js');const T=window.Traffic;
const deviation=q=>{const mean=q.reduce((s,c)=>s+c.v,0)/q.length;return Math.sqrt(q.reduce((s,c)=>s+(c.v-mean)**2,0)/q.length);};
let minStep=Infinity,minSpeed=Infinity,previous=T.sample(0);
for(let k=1;k<=3199;k++){
  const q=T.sample(k*.1);
  q.forEach((c,i)=>{minStep=Math.min(minStep,c.s-previous[i].s);minSpeed=Math.min(minSpeed,c.v);});previous=q;
}
let waveTravel=0,maxWaveStep=-Infinity;
for(let t=210;t<240;t+=.1){const d=T.wrap(T.jam(t+.1).position-T.jam(t).position);waveTravel+=d;maxWaveStep=Math.max(maxWaveStep,d);}
const report={illustrative_model:true,parameters_not_fitted_to_experiment:true,audit:T.audit,
  minimum_forward_step:minStep,minimum_speed:minSpeed,wave_210_to_240:{distance:waveTravel,max_step:maxWaveStep},
  final_speed_deviation:{dense:deviation(T.sample(300)),sparse:deviation(T.sample(300,true))},
  gold_passage:{entry:T.sample(201)[T.goldId],stopped:T.sample(213)[T.goldId],exited:T.sample(236)[T.goldId]}};
report.checks={no_body_overlap:T.audit.dense.minGap>0&&T.audit.sparse.minGap>0,no_reversing:minStep>=-1e-7&&minSpeed>=0,
  wave_moves_upstream:waveTravel<0&&maxWaveStep<0,gold_stops_and_leaves:report.gold_passage.entry.v>4&&report.gold_passage.stopped.v===0&&report.gold_passage.exited.v>4,
  sparse_perturbation_decays:report.final_speed_deviation.sparse<.05,dense_wave_forms:report.final_speed_deviation.dense>2};
const out=path.join(__dirname,'build/review/model_audit.json');fs.mkdirSync(path.dirname(out),{recursive:true});fs.writeFileSync(out,JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report));if(!Object.values(report.checks).every(Boolean))process.exitCode=1;
