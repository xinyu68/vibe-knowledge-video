(() => {
'use strict';
const W=1920,H=1080,can=document.getElementById('stage'),c=can.getContext('2d',{alpha:false});
const P={bg:'#080e18',paper:'#080e18',ink:'#f0f3f4',soft:'#a6b4c5',line:'#395268',red:'#f17a61',olive:'#62c9cf',light:'#182738',gold:'#eac27b',blue:'#79b9de'};
const TAU=Math.PI*2,T=511/30,PLAN=window.FILM_PLAN;
const clamp=(v,a=0,b=1)=>Math.min(b,Math.max(a,v));
const mix=(a,b,p)=>a+(b-a)*p;
const sm=(a,b,t)=>{const v=clamp((t-a)/(b-a));return v*v*(3-2*v)};
const ease=p=>1-Math.pow(1-clamp(p),3);
const fade=(t,a,b,fi=.35,fo=.3)=>sm(a,a+fi,t)*(1-sm(b-fo,b,t));
const rgba=(h,a)=>{const x=parseInt(h.slice(1),16);return `rgba(${x>>16},${(x>>8)&255},${x&255},${a})`};
let boxes=[],checking=false,NOW=0;
function layer(a,fn){if(a<=0)return;c.save();c.globalAlpha*=clamp(a);fn();c.restore()}
function txt(s,x,y,size=36,col=P.ink,align='center',font='serif',weight=500,alpha=1){
 if(alpha<=0)return;c.save();c.globalAlpha*=alpha;c.fillStyle=col;c.textAlign=align;c.textBaseline='alphabetic';
 c.font=`${font==='italic'?'italic ':''}${weight} ${size}px ${font==='serif'?'FilmSerif':'FilmLatin'}`;
 c.fillText(s,x,y);if(checking&&c.globalAlpha>.4){const m=c.measureText(s),mx=c.getTransform(),xx=x-(align==='center'?m.width/2:align==='right'?m.width:0),yy=y-m.actualBoundingBoxAscent,ww=m.width,hh=m.actualBoundingBoxAscent+m.actualBoundingBoxDescent;const points=[[xx,yy],[xx+ww,yy],[xx,yy+hh],[xx+ww,yy+hh]].map(([a,b])=>({x:mx.a*a+mx.c*b+mx.e,y:mx.b*a+mx.d*b+mx.f}));const xs=points.map(v=>v.x),ys=points.map(v=>v.y);boxes.push({s,x:Math.min(...xs),y:Math.min(...ys),w:Math.max(...xs)-Math.min(...xs),h:Math.max(...ys)-Math.min(...ys)})}c.restore();
}
function tracked(s,x,y,size,gap,col=P.ink,alpha=1){const arr=Array.from(s);const total=arr.length*size+(arr.length-1)*gap;arr.forEach((v,i)=>txt(v,x-total/2+size/2+i*(size+gap),y,size,col,'center','serif',650,alpha))}
function line(points,col=P.line,width=2,alpha=1,dash=[]){c.save();c.globalAlpha*=alpha;c.strokeStyle=col;c.lineWidth=width;c.setLineDash(dash);c.beginPath();points.forEach((p,i)=>i?c.lineTo(...p):c.moveTo(...p));c.stroke();c.restore()}
function rect(x,y,w,h,fill=P.light,stroke=null,r=0){c.beginPath();r?c.roundRect(x,y,w,h,r):c.rect(x,y,w,h);if(fill){c.fillStyle=fill;c.fill()}if(stroke){c.strokeStyle=stroke;c.lineWidth=1.5;c.stroke()}}
function ring(x,y,r,col=P.red,a=1,w=2){c.save();c.globalAlpha*=a;c.strokeStyle=col;c.lineWidth=w;c.beginPath();c.ellipse(x,y,r,r*.965,-.025,0,TAU);c.stroke();c.restore()}
function arrow(x1,y1,x2,y2,col=P.soft,a=1){line([[x1,y1],[x2,y2]],col,2,a);const an=Math.atan2(y2-y1,x2-x1);line([[x2-13*Math.cos(an-.5),y2-13*Math.sin(an-.5)],[x2,y2],[x2-13*Math.cos(an+.5),y2-13*Math.sin(an+.5)]],col,2,a)}
function paperPanel(x,y,w,h,a=1){layer(a,()=>{c.save();c.shadowColor='rgba(63,49,25,.15)';c.shadowBlur=34;c.shadowOffsetY=12;rect(x,y,w,h,'#f5ecd9',null,2);c.restore();rect(x,y,w,h,null,'#c0b39a',2);line([[x+22,y+15],[x+w-22,y+15]],'#fff9e9',2,.6)})}
let seed=42017;const rand=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296};
const paper=document.createElement('canvas');paper.width=W;paper.height=H;const pc=paper.getContext('2d');
const bg=pc.createRadialGradient(960,420,70,960,540,1200);bg.addColorStop(0,'#14283a');bg.addColorStop(.65,'#0a1421');bg.addColorStop(1,'#040910');pc.fillStyle=bg;pc.fillRect(0,0,W,H);
for(let i=0;i<52000;i++){const x=rand()*W,y=rand()*H;pc.fillStyle=i%3?'rgba(24,49,69,.035)':'rgba(151,187,213,.035)';pc.fillRect(x,y,.5+rand()*1.6,.4+rand()*1.3)}
for(let i=0;i<1700;i++){const x=rand()*W,y=rand()*H;pc.strokeStyle='rgba(61,93,121,.025)';pc.lineWidth=.5;pc.beginPath();pc.moveTo(x,y);pc.lineTo(x+rand()*9-4,y+rand()*2-1);pc.stroke()}
const grain=document.createElement('canvas');grain.width=320;grain.height=180;const gc=grain.getContext('2d'),id=gc.createImageData(320,180);for(let i=0;i<id.data.length;i+=4){const v=rand()*255;id.data[i]=id.data[i+1]=id.data[i+2]=v;id.data[i+3]=6}gc.putImageData(id,0,0);
function background(){c.drawImage(paper,0,0)}
function finish(t){c.save();c.globalAlpha=.19;c.drawImage(grain,0,0,W,H);c.restore();const v=c.createRadialGradient(960,500,480,960,540,1120);v.addColorStop(0,'rgba(0,3,9,0)');v.addColorStop(1,'rgba(0,3,9,.32)');c.fillStyle=v;c.fillRect(0,0,W,H)}
function shape(cc,pts,fill,stroke,w=1.5){cc.beginPath();pts.forEach((p,i)=>i?cc.lineTo(...p):cc.moveTo(...p));cc.closePath();if(fill){cc.fillStyle=fill;cc.fill()}if(stroke){cc.strokeStyle=stroke;cc.lineWidth=w;cc.stroke()}}
function airframe(ghost){const out=document.createElement('canvas');out.width=800;out.height=650;const z=out.getContext('2d');z.translate(400,320);const edge=ghost?'#90b2c9':'#2b526d';
 const metal=z.createLinearGradient(-140,-200,170,180);metal.addColorStop(0,ghost?'#2b4b62':'#85a8be');metal.addColorStop(.32,ghost?'#52758b':'#d1e2e8');metal.addColorStop(.52,ghost?'#28475c':'#4c7b97');metal.addColorStop(.72,ghost?'#436780':'#7da7b9');metal.addColorStop(1,ghost?'#233d51':'#2d526e');
 z.save();z.shadowColor='rgba(0,0,0,.72)';z.shadowBlur=16;z.shadowOffsetY=8;
 shape(z,[[-30,-83],[-320,8],[-341,49],[-42,20],[42,20],[341,49],[320,8],[30,-83]],metal,edge,2);
 shape(z,[[-16,160],[-127,211],[-133,239],[-12,215],[12,215],[133,239],[127,211],[16,160]],metal,edge,2);z.restore();
 z.beginPath();z.moveTo(0,-257);z.bezierCurveTo(-30,-241,-39,-175,-32,-67);z.lineTo(-18,197);z.quadraticCurveTo(0,263,18,197);z.lineTo(32,-67);z.bezierCurveTo(39,-175,30,-241,0,-257);z.closePath();z.fillStyle=metal;z.fill();z.strokeStyle=edge;z.lineWidth=2;z.stroke();
 shape(z,[[-16,-206],[16,-206],[24,-157],[-24,-157]],ghost?'#223d53':'#173a55',edge,1.5);
 z.strokeStyle=ghost?'#456782':'#c1eaf2';z.lineWidth=1;z.beginPath();z.moveTo(0,-205);z.lineTo(0,-157);z.moveTo(-20,-178);z.lineTo(20,-178);z.stroke();
 for(const side of [-1,1]){z.strokeStyle=rgba(edge,.3);z.lineWidth=1;for(let k=1;k<7;k++){const xx=side*(44+k*39);z.beginPath();z.moveTo(xx,-66+k*12);z.lineTo(xx,18+k*4);z.stroke()}z.beginPath();z.moveTo(side*37,-42);z.lineTo(side*318,29);z.moveTo(side*30,10);z.lineTo(side*320,39);z.stroke();
 for(let k=0;k<36;k++){const xx=side*(42+k*7.6),yy=-42+k*1.96;z.beginPath();z.arc(xx,yy,1.1,0,TAU);z.fillStyle=rgba(edge,.45);z.fill()}}
 for(let y=-125;y<190;y+=38){z.beginPath();z.moveTo(-29+y*.03,y);z.lineTo(29-y*.03,y);z.strokeStyle=rgba(edge,.23);z.stroke()}
 z.beginPath();z.moveTo(-2,120);z.lineTo(-2,232);z.strokeStyle=rgba(edge,.7);z.lineWidth=3;z.stroke();
 return out;
}
const BODY=airframe(false),GHOST=airframe(true);
const holes=[[-260,25],[-224,9],[-187,-7],[-144,-14],[-119,14],[119,2],[160,-11],[199,12],[247,25],[280,35],[-63,208],[52,211],[2,82]];
const AIR_MASK=new Path2D();
for(const poly of [
 [[-30,-83],[-320,8],[-341,49],[-42,20],[42,20],[341,49],[320,8],[30,-83]],
 [[-16,160],[-127,211],[-133,239],[-12,215],[12,215],[133,239],[127,211],[16,160]]
]){AIR_MASK.moveTo(...poly[0]);poly.slice(1).forEach(p=>AIR_MASK.lineTo(...p));AIR_MASK.closePath()}
AIR_MASK.moveTo(0,-257);AIR_MASK.bezierCurveTo(-30,-241,-39,-175,-32,-67);AIR_MASK.lineTo(-18,197);AIR_MASK.quadraticCurveTo(0,263,18,197);AIR_MASK.lineTo(32,-67);AIR_MASK.bezierCurveTo(39,-175,30,-241,0,-257);AIR_MASK.closePath();
const SMOKE=document.createElement('canvas');SMOKE.width=128;SMOKE.height=128;
{const s=SMOKE.getContext('2d'),g=s.createRadialGradient(64,64,2,64,64,64);g.addColorStop(0,'rgba(156,169,178,.55)');g.addColorStop(.4,'rgba(106,126,143,.26)');g.addColorStop(1,'rgba(57,76,96,0)');s.fillStyle=g;s.fillRect(0,0,128,128)}
function propeller(ex,t,power,ghost){
 c.save();c.translate(ex,-120);const speed=clamp(power),phase=t*speed*28+ex*.12;
 c.fillStyle=rgba(ghost?'#81a3b8':'#c9e8ed',.035+.105*speed);c.beginPath();c.ellipse(0,0,49,12,0,0,TAU);c.fill();
 const repeats=speed>.25?5:1;
 for(let k=0;k<repeats;k++){
   const theta=phase-k*.15*speed;
   for(let j=0;j<3;j++){const angle=theta+j*TAU/3,x=Math.cos(angle)*46,y=Math.sin(angle)*11;
    line([[Math.cos(angle)*5,Math.sin(angle)*1.3],[x,y]],ghost?'#789aad':'#c5dce3',3.2,(1-k/(repeats+1))*(.8-.35*speed));}
 }
 c.fillStyle=ghost?'#426078':'#527b91';c.beginPath();c.arc(0,0,5.5,0,TAU);c.fill();c.restore();
}
function engine(ex,t,power,ghost,damage){
 c.save();c.translate(ex,0);c.rotate(damage*.013*Math.sin(t*12+ex));
 const g=c.createLinearGradient(-22,0,22,0);g.addColorStop(0,ghost?'#29475b':'#426a83');g.addColorStop(.37,ghost?'#55778b':'#b0cbd6');g.addColorStop(1,ghost?'#234357':'#47738e');
 c.save();c.shadowColor='rgba(0,0,0,.35)';c.shadowBlur=7;c.shadowOffsetX=3;rect(-20,-117,40,154,g,ghost?'#7d9fb5':'#2b526d',18);c.restore();
 line([[-12,-76],[12,-76]],'#4c7185',1,.5);line([[-12,-58],[12,-58]],'#4c7185',1,.5);
 if(damage>.05){const heat=c.createRadialGradient(0,20,1,0,20,30);heat.addColorStop(0,rgba(P.red,.22*damage));heat.addColorStop(1,rgba(P.red,0));rect(-30,-10,60,60,heat)}
 c.restore();propeller(ex,t,power,ghost);
}
function plane(x,y,s=1,a=1,opt={}){layer(a,()=>{
 const t=opt.time??NOW,fly=!!opt.flying,damage=clamp(opt.damage??0),bank=clamp(opt.bank??0,-1,1),heading=opt.heading??0;
 const rpm=opt.rpm??(fly?1:0),lp=clamp(opt.leftPower??1)*rpm,rp=clamp(opt.rightPower??1)*rpm;
 c.save();c.translate(x,y);c.rotate(heading);c.scale(s,s);c.transform(1-Math.abs(bank)*.17,bank*.085,0,1,0,0);
 if(fly)c.translate(Math.sin(t*7.3)*damage*2,Math.sin(t*9.1)*damage*1.5);
 const smoke=clamp(opt.smoke??0),side=opt.smokeSide??-1;
 if(smoke>.001){for(let i=21;i>=0;i--){const q=(t*.39+i/22)%1,px=side*95+Math.sin(q*8+t*.85)*q*34,py=35+q*355,r=15+q*79;
   layer(smoke*(1-q)*.74,()=>c.drawImage(SMOKE,px-r,py-r,r*2,r*2));}
   line([[side*95,26],[side*95+Math.sin(t*7)*4,50],[side*95-3,72]],P.red,2.1,.4*smoke);
 }
 c.drawImage(opt.ghost?GHOST:BODY,-400,-320);
 engine(-95,t,lp,opt.ghost,damage*(1-clamp(opt.leftPower??1)));engine(95,t,rp,opt.ghost,damage*(1-clamp(opt.rightPower??1)));
 if(fly){
   const flap=Math.sin(t*2.1)*.3+bank;
   for(const sign of [-1,1]){const lift=sign*flap*5;
    shape(c,[[sign*148,25],[sign*288,42],[sign*286,48+lift],[sign*148,32+lift]],'#5a839a','#315973',1.2);
   }
   line([[-2,170],[bank*11,223]],'#b5d2df',3,.65);
   c.save();c.clip(AIR_MASK);const gx=-450+((t*.13)%1)*900,shine=c.createLinearGradient(gx-150,0,gx+150,0);shine.addColorStop(0,'rgba(205,235,246,0)');shine.addColorStop(.5,'rgba(205,235,246,.12)');shine.addColorStop(1,'rgba(205,235,246,0)');rect(gx-150,-270,300,530,shine);c.restore();
 }
 if(opt.scan!==undefined){const scanx=mix(-350,350,clamp(opt.scan));c.save();c.clip(AIR_MASK);const g=c.createLinearGradient(scanx-45,0,scanx+45,0);g.addColorStop(0,rgba(P.blue,0));g.addColorStop(.5,rgba('#c9f1ff',.55));g.addColorStop(1,rgba(P.blue,0));rect(scanx-45,-265,90,530,g);line([[scanx,-260],[scanx,260]],'#b5e7f3',2,.8);c.restore()}
 if(opt.armor){layer(opt.armor,()=>{for(const sign of [-1,1]){shape(c,[[sign*135,-25],[sign*290,21],[sign*287,43],[sign*133,12]],'rgba(98,201,207,.52)',P.olive,2);for(let k=0;k<5;k++)line([[sign*(150+k*26),-18+k*8],[sign*(150+k*26),15+k*4]],P.olive,1,.6)}})}
 if(opt.holes){holes.forEach(([hx,hy],i)=>{const alpha=clamp(opt.holes*14-i);layer(alpha,()=>{c.beginPath();c.ellipse(hx,hy,5.2,4.1,-.4,0,TAU);c.fillStyle=P.red;c.fill();line([[hx-8,hy-4],[hx-4,hy-2]],P.red,1,.6);ring(hx,hy,10,P.red,.27,1.1)})})}
 if(opt.critical){layer(opt.critical,()=>{[-95,95].forEach(ex=>rect(ex-25,-130,50,175,'rgba(241,122,97,.18)',P.red,19))})}
 if(opt.hit){layer(opt.hit,()=>{const hits=opt.smokeSide?[opt.smokeSide*95]:[-95,95];hits.forEach(ex=>{c.beginPath();c.arc(ex,-70,8,0,TAU);c.fillStyle=P.red;c.fill();ring(ex,-70,17,P.red,.7,2)})})}
 c.restore();
})}

function leader(x,y,xx,yy,s,a=1,col=P.soft){line([[x,y],[xx,y],[xx,yy-28]],col,1.5,a);txt(s,xx,yy,30,col,'center','serif',500,a)}
function modelNote(t){if(t>=16.433&&t<22.1)return;if(t>=8.4&&t<119.1)txt('飞机、弹孔与结果为简化示意',92,69,24,P.soft,'left','serif',400,fade(t,8.4,119.1,.5,.5))}
function stamp(x,y,r=46,a=1,label='留'){layer(a,()=>{ring(x,y,r,P.red,1,2.7);ring(x,y,r-6,P.red,.65,1);txt(label,x,y+14,r*.62,P.red,'center','serif',650)})}
function book(x,y,s=1,a=1,open=0,success=true){layer(a,()=>{c.save();c.translate(x,y);c.scale(s,s);c.save();c.shadowColor='rgba(58,45,27,.2)';c.shadowBlur=30;c.shadowOffsetY=18;shape(c,[[-180,-225],[160,-225],[184,-205],[184,236],[-158,236],[-180,214]],'#d7c8a9','#8b8068',2);c.restore();
 for(let j=0;j<7;j++)line([[-154,215+j*2.4],[179,215+j*2.4]],'#9f957b',1,.4);
 rect(-180,-225,343,440,success?'#65715c':'#b8ae97','#515a4c',3);rect(-174,-222,23,435,success?'#4e5b48':'#978e79');
 line([[-139,-210],[-139,198]],success?'#b9bca2':'#e9dcc2',1,.45);rect(-115,-158,226,264,null,success?'#d2cbb2':'#e7d9bb');
 txt(success?'成功经验':'未完的记录',0,-50,success?47:39,success?'#eee4c8':'#4b5144','center','serif',600);txt(success?'那些留下的故事':'同样做过的人',0,12,26,success?'#ddd8c0':'#626752');
 if(open){layer(open,()=>{shape(c,[[164,-225],[365,-206],[365,218],[164,215]],'#f3ead4','#b9ad93',1.5);for(let j=0;j<6;j++){line([[206,-139+j*42],[337-j%2*22,-139+j*42]],'#a49d89',1.5,.7);if(j<3)line([[187,-143+j*42],[193,-137+j*42],[205,-154+j*42]],P.olive,2.3)}})}
 c.restore()})}
function glow(x,y,r,col=P.blue,a=.25){if(a<=0)return;c.save();const g=c.createRadialGradient(x,y,0,x,y,r);g.addColorStop(0,rgba(col,a));g.addColorStop(.34,rgba(col,a*.34));g.addColorStop(1,rgba(col,0));c.fillStyle=g;c.fillRect(x-r,y-r,r*2,r*2);c.restore()}
function panel(x,y,w,h,a=1){layer(a,()=>{c.save();c.shadowColor='rgba(0,0,0,.45)';c.shadowBlur=35;c.shadowOffsetY=15;const g=c.createLinearGradient(x,y,x+w,y+h);g.addColorStop(0,'#20364a');g.addColorStop(1,'#101d2b');rect(x,y,w,h,g,P.line,14);c.restore();line([[x+25,y+2],[x+w-25,y+2]],P.blue,1,.3)})}
function label(s,x,y,col=P.soft,size=31,alpha=1){txt(s,x,y,size,col,'center','serif',500,alpha)}
function flightpath(points,t,col=P.gold,a=1){line(points,col,2,a*.5,[8,10]);for(const [x,y] of [points[0],points[points.length-1]]){glow(x,y,45,col,.13*a);ring(x,y,8,col,a,2)}const p=clamp(t)*(points.length-1),i=Math.min(points.length-2,Math.floor(p)),q=p-i;glow(mix(points[i][0],points[i+1][0],q),mix(points[i][1],points[i+1][1],q),28,col,.38*a)}
function contourMap(a=1){layer(a,()=>{
 const islands=[[[170,355],[260,310],[305,227],[388,215],[422,300],[390,380],[465,425],[440,506],[349,549],[310,641],[230,675],[180,603],[205,507],[160,420]],[[535,282],[674,211],[853,224],[945,274],[1118,240],[1270,311],[1420,297],[1580,400],[1738,470],[1680,591],[1510,625],[1370,580],[1230,648],[1040,604],[905,664],[742,588],[652,493],[566,422]]];
 islands.forEach(pts=>{shape(c,pts,'#182d40','#36546a',2);c.save();c.clip();for(let i=0;i<19;i++)line([[110,180+i*35],[1810,220+i*35]],'#496477',1,.17);c.restore()});
 for(let i=0;i<9;i++)line([[160+i*200,170],[160+i*200,760]],'#365268',1,.18);
 for(let i=0;i<6;i++)line([[150,200+i*110],[1780,200+i*110]],'#365268',1,.18);
 });}

const api={c,W,H,P,TAU,T,clamp,mix,sm,ease,fade,rgba,layer,txt,tracked,line,rect,ring,arrow,plane,glow,shape,panel,label,flightpath,contourMap};
const OPEN=window.MOTION_OPENING(api),ENDSC=window.MOTION_ENDING(api);
const {history,inspect,report,roster,conditions}=window.MOTION_INSPECTION(api);
const {flight,empty,compare,gate}=window.MOTION_MECHANISM(api);
const SC=[
 {s:0,fn:OPEN.intro},{s:4.2,fn:OPEN.shop,mode:'iris',at:[960,410]},
 {s:8.4,fn:OPEN.hook,mode:'iris',at:[960,425]},
 {s:T,fn:OPEN.anchor,mode:'impact'},
 {s:22.1,fn:history,mode:'iris',at:[960,450]},
 {s:26.51,fn:inspect,mode:'same'},
 {s:42.553,fn:report,mode:'same'},
 {s:51.882,fn:roster,mode:'wipe'},
 {s:57.09,fn:flight,mode:'wipe'},
 {s:77.354,fn:empty,mode:'iris',at:[1400,405]},
 {s:93.567,fn:compare,mode:'impact'},
 {s:99.753,fn:gate,mode:'line'},
 {s:111.417,fn:conditions,mode:'line'},
 {s:119.099,fn:ENDSC.life,mode:'iris',at:[960,440]},
 {s:142.736,fn:ENDSC.runway,mode:'line'},
 {s:148.862,fn:ENDSC.closing,mode:'iris',at:[960,450]},
 {s:154.279,fn:ENDSC.ending,mode:'line'}
];
function scene(t){let i=0;while(i<SC.length-1&&t>=SC[i+1].s)i++;const sc=SC[i],u=(t-sc.s)/.55;
 if(i===0||u>=1||sc.mode==='same'||sc.mode==='impact'){sc.fn(t);return}
 const p=sm(0,1,u);SC[i-1].fn(sc.s-1/30);c.save();c.beginPath();
 if(sc.mode==='iris'){const [x,y]=sc.at||[960,450];c.arc(x,y,2+2250*p,0,TAU)}
 else if(sc.mode==='line'){const band=1080*p;c.rect(0,510-band/2,W,band+55*p)}
 else{c.rect(0,0,W*p,H)}
 c.clip();background();sc.fn(t);c.restore();
}
function subtitle(t){const s=PLAN.subtitles.find(s=>t>=s.start&&t<s.end);if(!s)return;const a=fade(t,s.start,s.end,.18,.22);layer(a,()=>{const g=c.createLinearGradient(0,845,0,1080);g.addColorStop(0,'rgba(4,8,15,0)');g.addColorStop(.38,'rgba(4,8,15,.78)');g.addColorStop(1,'rgba(4,8,15,.89)');rect(0,845,W,235,g);c.save();c.shadowColor='rgba(0,0,0,.7)';c.shadowBlur=8;txt(s.zh,960,930,49,P.ink,'center','serif',570);txt(s.en,960,988,29,'#b9c5d1','center','italic',400);c.restore()})}
function draw(t){NOW=t;boxes=[];c.resetTransform();c.globalAlpha=1;background();c.save();
 if(t>=16.4&&t<T){const a=1-sm(16.4,16.9,t);layer(a,()=>OPEN.hook(16.4));const g=c.createLinearGradient(0,0,0,H);g.addColorStop(0,'rgba(2,5,10,.65)');g.addColorStop(1,'rgba(2,5,10,.65)');layer(sm(16.4,16.9,t),()=>rect(0,0,W,H,g));}
 else scene(t);c.restore();
 if(t<16.4||t>=22.1&&t<119.099)txt('画面与结果为简化示意',80,64,24,P.soft,'left','serif',450,.8);
 subtitle(t);finish(t);if(t>157.3){layer(sm(157.3,159.25,t),()=>{c.fillStyle='#080e18';c.fillRect(0,0,W,H)})}window.LAST_BOXES=boxes;
}
window.render=window.seek=t=>draw(clamp(t,0,PLAN.duration));window.END=PLAN.frames/30;window.FPS=30;window.READY=false;
window.audit=t=>{checking=true;draw(t);checking=false;return boxes.filter(b=>b.x<40||b.y<28||b.x+b.w>W-40||b.y+b.h>H-36)};
Promise.all([document.fonts.load('570 49px FilmSerif','没回来的飞机缺席'),document.fonts.load('400 40px FilmLatin','Knowledge'),document.fonts.load('italic 400 29px FilmLatin','Knowledge')]).then(()=>{draw(0);window.READY=true}).catch(error=>console.error(error));
})();
