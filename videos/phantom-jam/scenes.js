(() => {
  'use strict';
  const {ctx,clamp,lerp,smooth,text,line}=F, P=window.FILM_PLAN, T=Traffic, TAU=Math.PI*2;
  const C={white:'#edf1ef',muted:'#9dadb8',gold:'#e8bf78',cyan:'#7cc4d8',red:'#f27861'};
  function interp(t,rows){if(t<=rows[0][0])return rows[0][1];for(let i=1;i<rows.length;i++){const a=rows[i-1],b=rows[i];if(t<=b[0])return lerp(a[1],b[1],(t-a[0])/(b[0]-a[0]));}return rows.at(-1)[1];}
  function story(t){return interp(t,P.story_knots||[[0,0],[159.25,159.25]]);}
  function actual(s){return interp(s,(P.story_knots||[[0,0],[159.25,159.25]]).map(a=>[a[1],a[0]]));}
  function top(k,title,note='机制示意 · 时间已压缩'){
    text(k,110,80,23,C.gold,{align:'left'});text(note,1810,80,21,C.muted,{align:'right'});
    text(title,110,156,43,C.white,{align:'left'});
  }
  function arrow(points,color,width=4){
    const p=points.filter(Boolean);if(p.length<2)return;line(p,color,width);
    const a=p.at(-2),b=p.at(-1),v=Math.atan2(b[1]-a[1],b[0]-a[0]);
    line([[b[0]-15*Math.cos(v-.45),b[1]-15*Math.sin(v-.45)],b,[b[0]-15*Math.cos(v+.45),b[1]-15*Math.sin(v+.45)]],color,width);
  }
  function ringArrow(theta,arc,r,color){
    const pts=Array.from({length:35},(_,i)=>{const a=theta+arc*i/34;const q=World.project([r*Math.cos(a),.10,r*Math.sin(a)]);return q&&q.slice(0,2);});arrow(pts,color,3.5);
  }
  const ringCam={x:40,y:73,z:-83,target:[0,0,0],fov:44,cy:470};
  function ring(t,options={}){
    const j=T.jam(t),a=Math.PI/2-j.angle;
    const markers=options.wave?[{type:'arc',radius:T.R+3,start:a-.52,end:a+.52,color:'rgba(238,99,78,.75)'}]:[];
    World.render({mode:'ring',cars:T.cars(t,options),ringRadius:T.R,roadWidth:5.2,lamps:false,time:t,markers,
      camera:{...ringCam,...(options.camera||{})}});
  }
  function road(t,camera,center=856,extra={}){
    const data=T.sample(t),cars=T.cars(t,{mode:'road',center}).map(c=>({...c,wheelPhase:data[c.id].s}));
    World.render({mode:'road',cars,camera,roadWidth:5.2,roadLength:150,lamps:true,time:t,...extra});
  }
  function opening(s){
    const q=smooth(4,15.9,s),u=205+Math.min(s,16.4)*.8;
    road(u,{x:lerp(6.7,19,q),y:lerp(4.7,24,q),z:lerp(-8,17,q),target:[0,.45,lerp(5,48,q)],fov:45,cy:470});
    top('01  /  一次突然的停顿','没有事故，车怎么就停了？');
    const a=smooth(8,10,s);if(a>0){text('前方没有障碍',1400,320,34,C.cyan,{alpha:a});text('车流仍会停下来',1400,368,26,C.muted,{alpha:a});}
  }
  function impact(s){
    road(220,{x:36,y:43,z:-35,target:[0,0,20],fov:47,cy:500});
    ctx.fillStyle='rgba(4,10,18,.76)';ctx.fillRect(0,0,1920,1080);
    const age=s-511/30,flash=Math.exp(-age*9);
    const g=ctx.createRadialGradient(960,420,5,960,420,650);g.addColorStop(0,`rgba(244,111,82,${.2+flash*.22})`);g.addColorStop(1,'rgba(244,111,82,0)');ctx.fillStyle=g;ctx.fillRect(0,0,1920,1080);
    ctx.strokeStyle=`rgba(239,160,120,${Math.max(0,.6-age*.18)})`;ctx.lineWidth=2;ctx.beginPath();ctx.ellipse(960,420,170+age*245,78+age*92,0,0,TAU);ctx.stroke();
    text('无形的墙',960,460,174,C.gold,{weight:650});
    if(age>.6){text('幽灵堵车',960,560,37,C.white,{alpha:smooth(.6,1.1,age)});text('Phantom traffic jams',960,606,27,C.muted,{italic:true,alpha:smooth(.6,1.1,age)});}
    text('路是通的，慢行却在传播',960,740,35,C.white);
  }
  function naming(s){
    if(s<21.6){impact(s);return;}
    if(s<22.25){impact(21.599);ctx.save();ctx.beginPath();const p=smooth(21.6,22.25,s);ctx.ellipse(960,480,2100*p,1300*p,0,0,TAU);ctx.clip();}
    road(225+(s-21.6)*1.15,{x:30,y:34,z:-33,target:[0,0,18],fov:46,cy:470});
    top('02  /  看见慢行区','没有固定障碍，也可能形成拥堵');
    const pos=T.wrap(T.jam(225+(s-21.6)*1.15).position-856),p=World.project([0,1.2,pos]);
    if(p&&p[0]>600&&p[0]<1700&&p[1]>230&&p[1]<790)arrow([[390,370],[p[0]-25,p[1]-15]],C.red,2);
    text('传播的是慢行状态',350,320,32,C.red);text('车辆会离开，后车会加入',350,420,25,C.muted);
    if(s<22.25)ctx.restore();
  }
  function experiment(s){
    const q=clamp((s-32)/13),t=lerp(0,225,q);
    ring(t,{wave:q>.65});top('03  /  一条没有路口的环路','车流自己，形成了停走波','研究场景示意 · 非实验录像');
    text('2008 年发表的环路研究',960,365,31,C.muted);
    text('22 辆车',960,444,59,C.gold);text('周长约 230 米',960,502,36,C.white);
    text('无路口 · 无车辆汇入',960,555,26,C.muted);
    text('动画按说明用模型演示，未拟合原始轨迹',110,213,22,C.muted,{align:'left'});
  }
  function mechanism(s){
    const t=interp(s,[[45,110],[49,142],[54,172],[62,195],[67,205],[72,214],[77,225]]),q=smooth(56,75,s);
    road(t,{x:lerp(16,32,q),y:lerp(12,36,q),z:lerp(-22,-36,q),target:[0,0,18],fov:48,cy:490},T.jam(t).position);
    top(s<62?'04  /  一个微小变化':'05  /  变化逐渐放大',s<62?'前车减速，后车接着调整':'车流越密，留给调整的空间越少');
    text(s<54?'轻微减速':s<62?'逐车传递':s<69?'变化可能放大':'后车甚至停下',350,325,37,s<62?C.cyan:C.red);
    text('同一组跟驰模型 · 示意过程',350,380,22,C.muted);
    const p=World.project([0,1.4,0]);if(p&&p[1]<780)arrow([[445,420],[p[0]-30,p[1]-20]],s<62?C.cyan:C.red,2.5);
  }
  function directions(s){
    const t=226+(s-77)*1.0;ring(t,{wave:true});top('06  /  两个方向','车在向前，拥堵却在向后');
    ringArrow(2.7,.8,T.R-5,C.cyan);ringArrow(.3,-.8,T.R+5,C.red);
    text('车辆前行',960,390,40,C.cyan);text('慢行区后移',960,458,40,C.red);text('前端驶出，后端加入',960,527,28,C.muted);
  }
  function passage(s){
    const a=actual(s),t=interp(a,[[actual(94),199],[93.57,203],[94.6,210],[95.775,224.5],[96.032,226],[97.476,234],[98.02,236],[actual(109),240.5]]);
    const gold=T.sample(t)[T.goldId],z=T.wrap(gold.s-856),q=smooth(99,108,s);
    if(a<98.0){road(t,{x:lerp(9,25,q),y:lerp(6,29,q),z:z-lerp(12,33,q),target:[0,.35,z+lerp(5,15,q)],fov:46,cy:490});}
    else{
      if(a<98.6){road(t,{x:lerp(9,25,q),y:lerp(6,29,q),z:z-lerp(12,33,q),target:[0,.35,z+lerp(5,15,q)],fov:46,cy:490});ctx.save();ctx.beginPath();const p=smooth(98,98.6,a);ctx.ellipse(960,480,2100*p,1300*p,0,0,TAU);ctx.clip();}
      ring(t,{wave:true});ringArrow(.3,-.8,T.R+5,C.red);
      if(a<98.6)ctx.restore();
    }
    top('07  /  只盯住同一辆车','金色的车驶出，堵团仍然存在');
    const state=t<205?'驶入慢行区':t<225?'减速 · 停下':t<234?'重新加速':'驶出了堵团';
    if(a<98){text(state,350,310,42,C.gold);text('金车始终向前，没有倒车',350,367,25,C.muted);}
    else{text('金车已驶出',960,400,36,C.gold);text('后车仍在加入',960,466,34,C.red);text('堵团没有跟着消失',960,526,27,C.muted);}
  }
  function comparison(s){
    const t=interp(s,[[109,20],[111,80],[118,220],[123,250]]);
    for(let side=0;side<2;side++){
      ctx.save();ctx.beginPath();ctx.rect(side*960,0,960,1080);ctx.clip();
      ring(t,{lowDensity:side===0,gold:-1,wave:side===1,camera:{x:52,y:103,z:-112,target:[0,0,0],fov:45,cy:475,cx:480+side*960}});ctx.restore();
    }
    top('08  /  为什么有时会，有时不会','不是每一次减速，都会变成堵车');
    text('较疏车流',480,294,38,C.cyan);text('较密车流',1440,294,38,C.red);
    text('微小变化逐渐消退',480,755,30,C.cyan);text('在不稳定条件下放大',1440,755,30,C.red);
    text('同一微扰；密度、间距与跟驰响应共同影响结果',960,822,23,C.muted);line([[960,235],[960,790]],'rgba(157,180,196,.2)',1);
  }
  function boundary(s){
    const t=229+(s-123)*.65,g=T.sample(t)[T.goldId],z=T.wrap(g.s-856);
    road(t,{x:14,y:10,z:z-18,target:[0,.5,z+12],fov:48,cy:490});top('09  /  解释的边界','这只是拥堵的一种机制');
    ['事故','施工','车辆汇入'].forEach((v,i)=>text(v,300,320+i*63,34,C.muted,{alpha:smooth(123+i*1.5,124+i*1.5,s)}));
    text('不能简单归咎于一个司机',430,585,31,C.gold,{alpha:smooth(129,132,s)});
  }
  function ending(s){
    const q=smooth(139,153,s),t=interp(s,[[137,229],[151,238],[159.25,243]]),g=T.sample(t)[T.goldId],z=T.wrap(g.s-856);
    if(s<146.65)road(t,{x:lerp(8,47,q),y:lerp(5,58,q),z:z-lerp(12,52,q),target:[0,.4,z+lerp(6,20,q)],fov:46,cy:450});
    if(s>=146){
      if(s<146.65){ctx.save();ctx.beginPath();const p=smooth(146,146.65,s);ctx.ellipse(960,480,2100*p,1300*p,0,0,TAU);ctx.clip();}
      ring(t,{wave:true,camera:{x:44,y:84,z:-98,cy:445}});
      if(s<146.65)ctx.restore();
    }
    if(s<151)top('10  /  回到那次停顿','无形的墙，藏在相互影响里');
    if(s>=151){const a=smooth(151,153,s);text('看见整支队伍，才读懂这次停顿',960,880,43,C.gold,{alpha:a});
      text('参考：Sugiyama et al. (2008) · MIT Traffic · Treiber IDM',960,952,25,C.muted,{alpha:a});
      text('音乐：《千年之后（氛围版）》原谅他7次 · AI 合成配音：云健 · 模型示意',960,999,24,C.muted,{alpha:a});}
  }
  const bounds=[0,17.033333333333335,18,32,45,62,77,94,109,123,137];
  const renderers=[opening,impact,naming,experiment,mechanism,mechanism,directions,passage,comparison,boundary,ending];
  function sceneIndex(s){let i=0;while(i+1<bounds.length&&s>=bounds[i+1])i++;return i;}
  function content(s){const i=sceneIndex(s),at=bounds[i];
    if([32,45,77,94,109,123,137].includes(at)&&s<at+.65){
      renderers[i-1](at-.001);const p=smooth(at,at+.65,s);ctx.save();ctx.beginPath();ctx.ellipse(960,480,2100*p,1300*p,0,0,TAU);ctx.clip();renderers[i](s);ctx.restore();
    }else renderers[i](s);
  }
  function captions(t){
    const sub=P.subtitles.find(s=>t>=s.start&&t<s.end);if(!sub)return;
    const a=Math.min(smooth(sub.start,sub.start+.13,t),1-smooth(sub.end-.12,sub.end,t));
    const g=ctx.createLinearGradient(0,805,0,1080);g.addColorStop(0,'rgba(2,7,12,0)');g.addColorStop(.38,'rgba(2,7,12,.83)');g.addColorStop(1,'rgba(2,7,12,.97)');ctx.fillStyle=g;ctx.fillRect(0,805,1920,275);
    text(sub.zh,960,938,47,C.white,{alpha:a,shadow:true,maxWidth:1700,role:'subtitle'});
    text(sub.en,960,996,28,C.white,{alpha:a,italic:true,shadow:true,maxWidth:1720,role:'subtitle'});
  }
  function render(t){
    t=clamp(t,0,159.249999);ctx.setTransform(1,0,0,1,0,0);ctx.globalAlpha=1;F.boxes=[];const s=story(t);
    if(t>=16.4&&t<511/30){opening(16.399);ctx.fillStyle=`rgba(2,7,12,${.97*smooth(16.4,16.9,t)})`;ctx.fillRect(0,0,1920,1080);}
    else content(s);
    if(t<16.4||t>=17.9)captions(t);
    const fade=smooth(158.4,159.25,t);if(fade>0){ctx.fillStyle=`rgba(2,7,12,${fade})`;ctx.fillRect(0,0,1920,1080);}
  }
  window.render=window.seek=render;window.storyTime=story;
  window.auditBoxes=t=>{F.checking=true;render(t);F.checking=false;return F.boxes;};
  window.audit=t=>window.auditBoxes(t).filter(b=>b.x<35||b.y<26||b.x+b.w>1885||b.y+b.h>1048);
  Promise.all([document.fonts.load('500 48px FilmSerif'),document.fonts.load('italic 400 28px FilmLatin')]).then(()=>{render(0);window.READY=true;});
})();
