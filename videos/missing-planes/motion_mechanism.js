window.MOTION_MECHANISM = api => {
  'use strict';
  const {c,W,H,P,TAU,clamp,mix,sm,fade,rgba,layer,txt,tracked,line,rect,ring,arrow,plane,glow,shape,panel,label}=api;
  const PI=Math.PI;
  const BOUNDS={x:172,y:278,w:1603,h:528};
  const IDs=['A','B','C'];
  const wingHits=[61.56,61.78,62.0], arrivals=[65.55,64.85,64.15];
  const vitalHits=[66.489,66.78,67.08];
  const smooth=p=>{p=clamp(p);return p*p*(3-2*p)};

  function curve(points,u){
    const p=clamp(u),v=1-p;
    const [a,b,d,e]=points;
    const x=v*v*v*a[0]+3*v*v*p*b[0]+3*v*p*p*d[0]+p*p*p*e[0];
    const y=v*v*v*a[1]+3*v*v*p*b[1]+3*v*p*p*d[1]+p*p*p*e[1];
    const dx=3*v*v*(b[0]-a[0])+6*v*p*(d[0]-b[0])+3*p*p*(e[0]-d[0]);
    const dy=3*v*v*(b[1]-a[1])+6*v*p*(d[1]-b[1])+3*p*p*(e[1]-d[1]);
    return {x,y,heading:Math.atan2(dy,dx)+PI/2};
  }
  function curveLine(points,end,col=P.blue,alpha=.5,width=2){
    const pts=[];for(let j=0;j<=45;j++){const p=curve(points,clamp(end)*j/45);pts.push([p.x,p.y])}line(pts,col,width,alpha);
  }
  function dashedBox(x,y,w,h,col,a=1){
    c.save();c.globalAlpha*=a;c.strokeStyle=col;c.lineWidth=2;c.setLineDash([9,8]);c.beginPath();c.roundRect(x,y,w,h,12);c.stroke();c.restore();
  }
  function clipField(fn){c.save();c.beginPath();c.rect(175,285,1235,511);c.clip();fn();c.restore()}
  function impact(x,y,t,start,col=P.red,size=43){
    const p=(t-start)/.45;if(p<0||p>1)return;
    glow(x,y,size*(1+p*1.2),col,(1-p)*.45);
    ring(x,y,6+p*size,col,(1-p)*.85,3);
    for(let j=0;j<5;j++){const a=j*TAU/5+.4;line([[x+Math.cos(a)*(8+p*10),y+Math.sin(a)*(8+p*10)],[x+Math.cos(a)*(14+p*35),y+Math.sin(a)*(14+p*35)]],col,2,1-p)}
  }
  function localToWorld(x,y,s,heading,lx,ly){
    return {x:x+s*(lx*Math.cos(heading)-ly*Math.sin(heading)),y:y+s*(lx*Math.sin(heading)+ly*Math.cos(heading))};
  }
  function observationFrame(x,y,w,h,a=1,col=P.olive){
    const n=24;const corners=[[[x,y+n],[x,y],[x+n,y]],[[x+w-n,y],[x+w,y],[x+w,y+n]],[[x,y+h-n],[x,y+h],[x+n,y+h]],[[x+w-n,y+h],[x+w,y+h],[x+w,y+h-n]]];
    corners.forEach(pts=>line(pts,col,3,a));line([[x+45,y],[x+w-45,y]],col,1,.26*a);line([[x+45,y+h],[x+w-45,y+h]],col,1,.26*a);
  }
  function movingDashes(t,y,x1=220,x2=1330,a=.45){
    c.save();c.strokeStyle=rgba(P.blue,a);c.lineWidth=1.7;c.setLineDash([13,19]);c.lineDashOffset=-(t*37)%32;c.beginPath();c.moveTo(x1,y);c.lineTo(x2,y);c.stroke();c.restore();
  }
  function row(x,y,w,id,p,missing=false){
    const col=missing?P.soft:P.olive;
    rect(x,y,w,54,missing?'rgba(13,25,39,.6)':rgba(P.olive,.055+.07*p),rgba(missing?P.line:P.olive,.23+.3*p),8);
    txt(id,x+26,y+36,29,col,'left','latin',600);
    if(missing){line([[x+75,y+28],[x+w-30,y+28]],P.line,1.5,.65,[8,8]);return}
    layer(1-p,()=>{line([[x+75,y+28],[x+w-30,y+28]],P.line,1.5,.6,[8,8])});
    layer(p,()=>{line([[x+72,y+27],[x+82,y+37],[x+100,y+16]],P.olive,3);txt('已返航',x+118,y+36,28,P.ink,'left');});
  }
  function ledger(t,x=1435,y=294,filter=0){
    const height=mix(496,260,filter);
    panel(x,y,318,height,.82);label('返航登记',x+159,y+48,P.olive,34);
    for(let i=0;i<3;i++){
      const p=sm(arrivals[i],arrivals[i]+.34,t);row(x+18,y+72+i*60,282,IDs[i],p);
      const pulse=fade(t,arrivals[i],arrivals[i]+.7,.05,.45);glow(x+46,y+100+i*60,65,P.olive,.3*pulse);
    }
    layer(1-filter,()=>{
      line([[x+22,y+270],[x+296,y+270]],P.line,1,.65);
      for(let i=0;i<3;i++)row(x+18,y+290+i*60,282,['D','E','F'][i],0,true);
    });
  }
  function runway(t,x,y,a=1){
    layer(a,()=>{rect(x-31,y-100,62,200,'rgba(98,201,207,.07)',rgba(P.olive,.4),5);line([[x,y-83],[x,y+83]],P.olive,2,.6,[7,11]);
      for(let i=0;i<6;i++){const yy=y-84+i*33;glow(x-38,yy,12,P.gold,.24);glow(x+38,yy,12,P.gold,.24)}
    });
  }

  function flight(t){
    const filter=sm(71.478,74.3,t),summary=sm(72.2,73.5,t);
    txt('同样中弹，结果可能不同',960,170,66,P.ink,'center','serif',600);
    label('示意假设：两组中弹机会相同',960,229,P.soft,29);
    const frameBottom=mix(806,583,filter);
    observationFrame(BOUNDS.x,BOUNDS.y,BOUNDS.w,frameBottom-BOUNDS.y,.55+.35*filter);
    layer(1-filter,()=>{
      label('机翼受伤',305,327,P.olive,32);label('要害受损',305,582,P.red,32);
      movingDashes(t,454);movingDashes(t,709);runway(t,1310,418);
      label('基地',1310,313,P.olive,30);
      line([[1350,292],[1350,787]],P.line,1,.45);
    });
    clipField(()=>{
      layer(1-summary,()=>{
        for(let i=0;i<3;i++){
          const hit=wingHits[i],arrival=arrivals[i],x0=285+i*196,xh=665+i*140;
          // A nearly constant approach speed preserves the queue; no easing into a shared parking point.
          let x=t<hit?mix(x0,xh,sm(57.09,hit,t)):mix(xh,1303,clamp((t-hit)/(arrival-hit)));
          const y=407+Math.sin(t*2.2+i)*2.2;
          const land=sm(arrival-.12,arrival,t),a=1-land;
          plane(x,y,.205,a,{time:t,heading:PI/2,flying:true,bank:.06*Math.sin(t*2+i),holes:sm(hit,hit+.34,t),damage:.08*sm(hit,hit+.4,t)});
          const wound=localToWorld(x,y,.205,PI/2,190,5);impact(wound.x,wound.y,t,hit,P.red,35);
          if(t>hit&&t<arrival+.1)line([[xh-50,461+i*4],[Math.max(xh-50,x-70),461+i*4]],P.olive,1,.22);
          layer(a,()=>txt(IDs[i],x,y+97,29,P.soft,'center','latin',500));
          if(t>=arrival&&t<arrival+.52){const q=sm(arrival,arrival+.52,t),px=mix(1310,1438,q),py=mix(407,394+i*60,q);glow(px,py,27,P.olive,.45*(1-q));}
        }
        for(let i=0;i<3;i++){
          const hit=vitalHits[i],q=clamp((t-hit)/3.1),x0=285+i*196,xh=570+i*250;
          const before=curve([[x0,656],[x0+130,654],[xh-70,654],[xh,656]],sm(57.09,hit,t));
          // Separate turning corridors prevent the damaged aircraft from converging visually.
          const pts=[[xh,656],[xh+90,656],[xh+145,768],[xh+170,885]],after=curve(pts,q);
          const p=t<hit?before:after,dam=sm(hit,hit+.7,t),a=1-sm(hit+2.7,hit+3.25,t);
          if(t>=hit)curveLine(pts,q,P.red,.4*a,2);
          plane(p.x,p.y,.224,a,{time:t,heading:p.heading,flying:true,bank:.48*dam,hit:dam,damage:dam*.8,rightPower:1-.93*dam,leftPower:1-.22*dam,smoke:dam*.58,smokeSide:1});
          const wound=localToWorld(p.x,p.y,.224,p.heading,95,-70);impact(wound.x,wound.y,t,hit,P.red,38);
          layer(a,()=>txt(['D','E','F'][i],p.x-68,p.y+15,29,P.soft,'center','latin',500));
        }
      });
    });
    ledger(t,1435,294,filter);
    layer(summary,()=>{
      plane(700,439,.42,1,{time:t,holes:1,scan:sm(72.2,74.6,t)});
      label('返航者的损伤图',1000,374,P.ink,38);
      label('伤口集中在机翼与尾部',1040,435,P.soft,30);
      arrow(1380,470,1115,470,P.olive,.65);
      ring(740,408,35,P.gold,.8,2);
    });
    layer(filter,()=>{
      const g=c.createLinearGradient(0,frameBottom,0,830);g.addColorStop(0,'rgba(8,14,24,.0)');g.addColorStop(.35,'rgba(8,14,24,.75)');g.addColorStop(1,'rgba(8,14,24,.92)');rect(180,frameBottom+8,1590,830-frameBottom,g);
      label('只把返航者装进观察窗口',960,682,P.gold,41);
      label('未返航者，没有留下同样的损伤记录',960,744,P.soft,30);
    });
  }

  function empty(t){
    const reveal=sm(83.49,86.0,t),whole=sm(89.327,91.4,t),x=mix(655,535,reveal),s=mix(1.0,.85,reveal);
    const w=mix(982,1598,reveal),boundsX=173;
    observationFrame(boundsX,263,w,543,.65,P.olive);
    glow(x,479,440,P.blue,.13);plane(x,490,s,1,{time:t,holes:1,scan:sm(77.7,80.5,t)});
    const ex=x+95*s,ey=490-75*s;ring(ex,ey,51,P.gold,.85,2.6);glow(ex,ey,80,P.gold,.13);
    layer(1-sm(82.9,83.49,t),()=>{
      txt('没有弹孔，意味着什么？',960,176,62,P.ink,'center','serif',600);
      label('返航者的图上',1450,368,P.soft,32);
      label('这里几乎没有伤痕',1450,431,P.gold,36);
      line([[ex+54,ey],[1240,ey],[1240,385]],P.gold,2,.6);
      label('这份记录，只来自回来的飞机',660,785,P.soft,31);
    });
    layer(reveal,()=>{
      txt('把另一种可能放回视野',960,176,61,P.ink,'center','serif',600);
      line([[960,302],[960,753]],P.line,1.5,.6);
      const x2=1360,y2=510,dam=sm(83.8,84.6,t),loss=sm(84.3,86.2,t);
      // This is explicitly hypothetical: missing planes' actual wound records remain unknown.
      label('示意推演',1360,310,P.red,32);
      plane(x2,y2,.60,1,{time:t,rpm:1,hit:dam,damage:dam*.7,rightPower:1-loss*.97,leftPower:1-loss*.25,smoke:.35*loss,smokeSide:1});
      const e2={x:x2+95*.60,y:y2-75*.60};impact(e2.x,e2.y,t,83.8,P.red,42);ring(e2.x,e2.y,43,P.red,.6,2);
      line([[ex+60,ey],[931,ey],[989,e2.y],[e2.x-50,e2.y]],P.gold,2,.4,[7,9]);
      label('要害受损，可能无法返航',1360,718,P.red,33);
      label('非真实遗漏记录，具体情况仍未知',1360,770,P.soft,28);
      label('已观察的返航损伤',535,762,P.olive,33);
    });
    layer(whole,()=>{
      // A broad bracket connects the observed and unobserved sides without inventing data.
      line([[245,223],[245,240],[1675,240],[1675,223]],P.gold,2,.7);
      glow(960,240,180,P.gold,.08);
    });
  }

  function compare(t){
    const p=sm(93.567,94.4,t),grow=sm(94.1,96.3,t),pulse=1-sm(93.567,94.5,t);
    glow(960,260,610,P.gold,.15*pulse);ring(960,268,30+620*sm(93.567,94.5,t),P.gold,pulse*.45,2.5);
    tracked('幸存 ≠ 全部',960,268,106,9,P.ink);line([[560,329],[1360,329]],P.gold,2,.8);
    const right=mix(930,1637,grow);observationFrame(282,383,right-282,386,.72,P.gold);
    layer(p,()=>{
      rect(322,437,582,243,rgba(P.olive,.05),rgba(P.olive,.3),14);
      label('已观察的返航者',613,421,P.olive,34);
      for(let i=0;i<3;i++){
        const z=sm(93.8+i*.17,94.5+i*.17,t);plane(420+i*195,mix(591,552,z),.218,z,{time:t,holes:1});
        label(IDs[i],420+i*195,656,P.soft,28);
      }
      label('留下了损伤记录',613,728,P.olive,32);
    });
    layer(grow,()=>{
      dashedBox(1015,437,582,243,P.soft,.5);label('其余出发者',1306,421,P.soft,34);
      for(let i=0;i<3;i++){
        const xx=1111+i*195,qq=sm(94.6+i*.3,95.4+i*.3,t);
        layer(qq,()=>{plane(xx,552,.218,.4,{time:t,ghost:true});ring(xx,552,33,P.gold,.8,1.5);txt('?',xx,565,40,P.gold,'center','latin',600)});
      }
      label('具体损伤信息未齐',1306,728,P.soft,32);
    });
    label('出发名册，比返航记录更大',960,817,P.gold,35,sm(96.4,97.1,t));
  }

  function gate(t){
    const question=sm(106.368,107.15,t),g=1020;
    txt('先看筛选的那道门',960,173,67,P.ink,'center','serif',600);
    label('观察条件：能够返航',960,234,P.soft,30);
    glow(g,474,250,P.olive,.1);
    line([[g-16,308],[g-16,746]],P.olive,4);line([[g-45,308],[g+30,308]],P.olive,3);line([[g-45,746],[g+30,746]],P.olive,3);
    label('进入观察',g,801,P.olive,32);
    label('出发者',365,314,P.soft,33);label('返航记录',1512,314,P.olive,34);
    movingDashes(t,478,240,1280,.25);movingDashes(t,701,240,960,.22);
    panel(1310,341,405,252,.75);
    const ends=[104.6,103.95,103.3];
    for(let i=0;i<3;i++){
      const start=99.753,arrive=ends[i],cross=arrive-.75,q=sm(start,arrive,t),pp=curve([[300+i*180,424],[690+i*100,424],[1140,424],[1375,394+i*65]],q);
      const scale=.21*(1-.82*sm(cross,arrive,t)),a=1-sm(arrive-.1,arrive+.12,t);
      if(t<arrive+.12)plane(pp.x,pp.y,scale,a,{time:t,heading:pp.heading,flying:true,holes:1,bank:.06*Math.sin(t*2+i)});
      row(1333,366+i*65,359,IDs[i],sm(arrive-.02,arrive+.3,t));
      const signal=fade(t,arrive-.75,arrive-.15,.08,.38);glow(g,428,68,P.olive,.23*signal);
      const miss=sm(101.2+i*.28,104.7+i*.18,t),route=[[300+i*180,642],[680+i*120,642],[870,706],[913,820+i*12]],lost=curve(route,miss);
      const lostAlpha=1-sm(103.6+i*.2,104.8+i*.2,t);
      clipField(()=>{
        curveLine(route,miss,P.red,.22*lostAlpha,1.5);
        plane(lost.x,lost.y,.21,lostAlpha,{time:t,heading:lost.heading,flying:true,ghost:true,hit:1,bank:.34,smoke:.22,rightPower:.12,leftPower:.7,smokeSide:1,damage:.7});
      });
    }
    layer(1-question,()=>{
      dashedBox(1310,627,405,150,P.line,.7);
      label('没有这份返航记录',1512,690,P.soft,31);
      label('≠ 没有发生过',1512,744,P.gold,31);
      line([[1037,650],[1258,650]],P.red,2,.4,[6,10]);
    });
    layer(question,()=>{
      panel(1250,620,525,172,.95);label('空白 ≠ 定论',1512,686,P.gold,46);label('真实原因仍需查证',1512,746,P.soft,31);
      ring(785,682,40,P.gold,.75,2);txt('?',785,697,49,P.gold,'center','latin',600);
      line([[835,682],[985,682]],P.gold,2,.5,[6,9]);
    });
  }
  return {flight,empty,compare,gate};
};
