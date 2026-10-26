window.MOTION_INSPECTION = api => {
  'use strict';
  const { c, W, H, P, TAU, T, clamp, mix, sm, ease, fade, rgba, layer,
    txt, tracked, line, rect, ring, arrow, plane, glow, shape, panel,
    label, flightpath, contourMap } = api;

  // These marks and aircraft are an explanatory model, not archival data.
  const marks = [[-260,25],[-224,9],[-187,-7],[-144,-14],[-119,14],
    [119,2],[160,-11],[199,12],[247,25],[280,35],[-63,208],[52,211],[2,82]];
  const groups = [
    { name: '左翼', indices: [0,1,2,3,4], start: 29.18, row: 415 },
    { name: '尾部', indices: [10,11], start: 29.85, row: 520 },
    { name: '右翼', indices: [5,6,7,8,9], start: 30.66, row: 625 }
  ];

  function heading(dx, dy) { return Math.atan2(dy, dx) + Math.PI / 2; }
  function hole(x, y, a = 1, r = 5.1) {
    layer(a, () => {
      c.beginPath(); c.ellipse(x, y, r, r * .79, -.35, 0, TAU);
      c.fillStyle = P.red; c.fill();
      ring(x, y, r * 1.9, P.red, .27, 1.1);
    });
  }
  function documentCard(x, y, w, h, a, known, progress = 1) {
    layer(a, () => {
      c.save(); c.shadowColor = 'rgba(0,0,0,.28)'; c.shadowBlur = 16;
      rect(x, y, w, h, known ? '#1b3448' : '#111e2d', null, 8); c.restore();
      line([[x+w-25,y],[x+w-25,y+25],[x+w,y+25]], P.soft, 1.5, .5);
      line([[x+15,y+20],[x+w-45,y+20]], known ? P.olive : P.line, 3, .75);
      if (known) {
        for (let j=0;j<3;j++) {
          const p=sm(j*.22,j*.22+.28,progress);
          line([[x+20,y+55+j*29],[x+20+(w-40)*p,y+55+j*29]], P.soft, 2, .6);
        }
        for (let j=0;j<4;j++) hole(x+26+j*(w-52)/3,y+h-32,sm(j*.15,j*.15+.3,progress),3.8);
      } else {
        c.save(); c.setLineDash([7,8]); c.strokeStyle = P.line; c.lineWidth=1.5;
        c.strokeRect(x+14,y+43,w-28,h-65); c.restore();
        txt('?',x+w/2,y+h*.69,Math.min(48,h*.35),P.gold,'center','serif',550);
      }
    });
  }
  function historyPose(t) {
    const q = sm(22.1,26.51,t), v=1-q;
    const a=[330,645], b=[780,575], d=[1345,397];
    return { x:v*v*a[0]+2*v*q*b[0]+q*q*d[0],
      y:v*v*a[1]+2*v*q*b[1]+q*q*d[1],
      angle:heading(2*v*(b[0]-a[0])+2*q*(d[0]-b[0]),
        2*v*(b[1]-a[1])+2*q*(d[1]-b[1])) };
  }
  function history(t) {
    contourMap(.85);
    txt('二战期间',190,174,66,P.ink,'left','serif',600);
    txt('伤痕随飞机，一起回到基地',194,229,33,P.soft,'left');
    const route=[];
    for(let i=0;i<=38;i++) { const f=historyPose(22.1+(26.51-22.1)*i/38); route.push([f.x,f.y]); }
    line(route,P.gold,2,.5,[7,11]);
    label('出发',330,748,P.soft,32); label('返回基地',1500,465,P.gold,32);
    // Runway lights lead into the destination; the nose follows the route tangent.
    for(let i=0;i<6;i++) {
      const x=1420+i*46,y=379-i*15;
      line([[x,y-17],[x+17,y+35]],P.line,1.5,.6);
      glow(x,y,18,P.gold,.28); ring(x,y,3,P.gold,.8,2);
    }
    const f=historyPose(t),p=sm(22.1,26.51,t);
    plane(f.x,f.y,.49,1,{time:t,heading:f.angle,flying:true,bank:.12*Math.sin(p*Math.PI),
      holes:1,rpm:.92,smoke:.14,leftPower:.82,rightPower:1});
  }

  function inspectPose(t) {
    const p=sm(26.51,27.6,t),a=historyPose(26.51);
    return {x:mix(a.x,660,p),y:mix(a.y,505,p),s:mix(.49,1.07,p),angle:mix(a.angle,0,p)};
  }
  function inspect(t) {
    const pose=inspectPose(t),settle=sm(26.51,27.6,t),q=sm(27.65,31.25,t);
    const scanX=mix(278,1035,q),critical=sm(36.607,37.4,t);
    const oldRecord=1-sm(36.607,36.88,t),newRecord=sm(36.94,37.4,t);
    if(settle<1)contourMap((1-settle)*.85);
    glow(660,495,540,P.blue,.14);
    plane(pose.x,pose.y,pose.s,1,{time:t,heading:pose.angle,holes:1-settle,
      flying:false,rpm:1-settle,scan:q,armor:0});
    layer(settle,()=>{
      const scanning=fade(t,27.55,31.7,.24,.3);
      const g=c.createLinearGradient(scanX-34,0,scanX+34,0);
      g.addColorStop(0,rgba(P.blue,0));g.addColorStop(.5,rgba(P.blue,.17));g.addColorStop(1,rgba(P.blue,0));
      layer(scanning,()=>{
        rect(scanX-34,264,68,523,g);
        line([[scanX,274],[scanX,778]],P.blue,2,.72);
        line([[scanX-12,264],[scanX+12,264]],P.blue,3,.9);
        line([[scanX-12,788],[scanX+12,788]],P.blue,3,.9);
      });
      marks.forEach(([x,y],i)=>{
        const wx=660+x*1.07,wy=505+y*1.07;
        const visible=sm(wx-28,wx+10,scanX);
        hole(wx,wy,visible);
        const pulse=visible*(1-sm(wx+16,wx+130,scanX));
        ring(wx,wy,16+8*pulse,P.red,pulse*.7,1.6);
      });
      panel(1180,274,565,462,.9);
      line([[1225,363],[1698,363]],P.line,1.5,.9);
      layer(oldRecord,()=>{
        txt('返航损伤记录',1462,337,40,P.ink,'center','serif',600);
        groups.forEach((g,gi)=>{
          const p=sm(g.start,g.start+.78,t),a=sm(g.start+.52,g.start+.86,t);
          label(g.name,1260,g.row+12,P.soft,32,a);
          line([[1322,g.row+25],[1697,g.row+25]],P.line,1,.55*a);
          g.indices.forEach((index,i)=>{
            const h=marks[index],px=660+h[0]*1.07,py=505+h[1]*1.07;
            const targetX=1370+i*(g.indices.length>2?61:108),targetY=g.row;
            if(p>0&&p<1) {
              const yy=mix(py,targetY,p)-Math.sin(p*Math.PI)*70;
              hole(mix(px,targetX,p),yy,Math.sin(p*Math.PI)*.75,5.7);
            }
            hole(targetX,targetY,a,5.7);
          });
          // A short travelling highlight shows that the damage has been entered.
          if(p>0&&p<1)ring(1711,g.row,8,P.olive,Math.sin(p*Math.PI),2);
        });
      });
      // Four plates settle separately, then lift away when the empty region is examined.
      const plates=[[-235,13,31.82],[-150,-11,32.43],[150,-6,33.06],[235,23,33.67]];
      plates.forEach(([px,py,start],i)=>{
        const arrive=sm(start,start+.7,t),leave=sm(36.607+i*.08,37.35+i*.08,t);
        const a=sm(start,start+.18,t)*(1-leave);
        if(!a)return;
        const x=660+px*1.07+(1-arrive)*(px<0?-105:105),y=505+py*1.07-95*(1-arrive)-45*leave;
        layer(a,()=>{
          c.save(); c.translate(x,y); c.rotate(px<0?-.21:.21);
          const shine=c.createLinearGradient(-43,-20,43,20);
          shine.addColorStop(0,'#a4c9cf');shine.addColorStop(.38,'#5d949f');shine.addColorStop(1,'#284f64');
          rect(-43,-18,86,36,shine,P.olive,3);
          for(const xx of [-34,34])for(const yy of [-10,10]){c.beginPath();c.arc(xx,yy,2.3,0,TAU);c.fillStyle='#c5e5df';c.fill();}
          c.restore();
          const tap=sm(start+.53,start+.68,t)*(1-sm(start+.7,start+.98,t));
          ring(x,y,51+22*tap,P.olive,tap*.45,1.5);
        });
      });
      const scanTitle=1-sm(31.538,31.92,t);
      txt('先看见伤口，再把它记下来',960,170,53,P.ink,'center','serif',600,scanTitle);
      txt('哪里受伤，就补哪里？',960,170,58,P.ink,'center','serif',600,sm(31.95,32.3,t)*(1-sm(36.607,36.94,t)));
      label('试着加厚受伤的位置',660,816,P.olive,33,sm(32,32.5,t)*(1-critical));
      layer(newRecord,()=>{
        const ex=660+95*1.07,ey=505-75*1.07,reveal=sm(37.1,38.2,t);
        ring(ex,ey,55,P.gold,.85,2.4);glow(ex,ey,90,P.gold,.12);
        const s=sm(37.1,38.3,t),sy=mix(ey-65,ey+67,s);
        line([[ex-38,sy],[ex+38,sy]],P.gold,2,fade(t,37.1,38.5,.2,.25));
        line([[ex+55,ey],[1118,ey],[1118,405],[1180,405]],P.gold,2,reveal*.7);
        txt('发动机区域',1462,337,40,P.ink,'center','serif',600);
        layer(reveal,()=>{
          c.save();c.strokeStyle=rgba(P.gold,.6);c.lineWidth=2;c.setLineDash([9,10]);c.strokeRect(1250,403,425,176);c.restore();
          txt('空白记录',1462,507,52,P.gold,'center','serif',550);
          txt('没有看到，不等于没有发生',1462,648,32,P.soft);
          label('还缺了谁？',1462,811,P.gold,44,sm(39,39.65,t));
        });
      });
      txt('可这里，没有伤口记录',960,170,58,P.ink,'center','serif',600,sm(37,37.5,t));
    });
  }

  function report(t) {
    const enter=sm(42.553,43.25,t),question=sm(46.804,47.55,t);
    const qTitle=1-sm(46.804,47.1,t);
    txt('沃尔德，研究这些返航记录',960,170,57,P.ink,'center','serif',600,qTitle);
    txt('这些记录，来自同一种结果',960,170,57,P.ink,'center','serif',600,sm(47.15,47.55,t));
    txt('Abraham Wald · 哥伦比亚大学统计研究组',960,225,29,P.soft);
    glow(335,485,285,P.blue,.15);
    plane(mix(660,330,enter),mix(505,490,enter),mix(1.07,.51,enter),1,{time:t,holes:1,flying:false,rpm:0});
    label('返回基地',330,704,P.olive,34,enter);
    arrow(500,489,616,489,P.olive,enter*.8);
    layer(enter,()=>{
      rect(652,277,1091,318,'rgba(25,48,63,.23)',null,12);
      line([[652,595],[652,277],[1743,277],[1743,595]],P.olive,2,.55);
      label('进入统计的记录',1197,319,P.olive,32,1-sm(46.804,47.05,t));
      label('仅包含返航者',1197,319,P.gold,35,sm(47.1,47.55,t));
      for(let i=0;i<3;i++) {
        const start=42.92+i*1.04,p=sm(start,start+.88,t);
        const x=mix(486,780+i*292,p),y=mix(428,352,p)-Math.sin(p*Math.PI)*62;
        const sc=mix(.35,1,p),w=203*sc,h=216*sc;
        documentCard(x,y,w,h,sm(start,start+.2,t),true,p);
        if(p>0&&p<1)line([[x-33,y+h*.6],[x-12,y+h*.6]],P.olive,2,Math.sin(p*Math.PI)*.6);
      }
    });
    layer(question,()=>{
      // A missing report is left blank: its unseen damage is not invented.
      line([[652,626],[1743,626]],P.line,1.5,.7,[8,10]);
      label('未返航者',330,773,P.gold,33);
      for(let i=0;i<3;i++) {
        const a=sm(47.25+i*.45,48.05+i*.45,t),x=780+i*292;
        documentCard(x,656,203,130,a,false);
      }
      txt('损伤记录缺席',1197,827,35,P.gold,'center','serif',500,sm(49,49.6,t));
    });
  }

  function roster(t) {
    txt('把整张出发名册展开',960,165,64,P.ink,'center','serif',600);
    txt('返航与否，都是出发后的结果',960,220,32,P.soft);
    label('返航者',275,421,P.olive,35);label('未返航者',275,661,P.gold,35);
    line([[420,543],[1690,543]],P.line,1.5,.8);
    for(let row=0;row<2;row++)for(let i=0;i<3;i++) {
      const x=630+i*405,y=405+row*245,start=52.04+row*.84+i*.3,p=sm(start,start+.66,t);
      panel(x-156,y-103,312,207,.48);
      const da=1-sm(.08,.57,p);
      documentCard(x-65,y-73-30*p,130,146,da,row===0);
      const pa=sm(.34,.95,p);
      plane(x,y,mix(.18,.31,pa),pa,{time:t,ghost:row===1,holes:row===0?1:0,hit:0,rpm:0,flying:false});
      if(row===1) {
        // Unknown damage must remain unknown even when the aircraft re-enters the roster.
        layer(pa,()=>{glow(x+103,y-48,34,P.gold,.16);txt('?',x+103,y-39,36,P.gold);});
        label('损伤记录缺席',x,y+111,P.gold,28,pa);
      } else label('有损伤记录',x,y+111,P.olive,28,pa);
    }
    label('先问：谁没被记录？',960,817,P.gold,37,sm(54.7,55.4,t));
  }

  function conditions(t) {
    txt('从线索走向判断',960,170,66,P.ink,'center','serif',600);
    const xs=[380,960,1540],colors=[P.blue,P.red,P.gold];
    const names=['中弹机会','受损后果','遗漏记录'];
    const questions=['哪些部位更易中弹？','受损怎样影响返航？','图外还有哪些结果？'];
    for(let i=0;i<3;i++) {
      const a=sm(111.417+i*.24,111.95+i*.24,t);
      const act=fade(t,111.6+i*2.1,114+i*2.1,.3,.5);
      layer(a,()=>{
        panel(xs[i]-246,270,492,491,.87);
        glow(xs[i],455,238,colors[i],.1+.12*act);
        line([[xs[i]-210,272],[xs[i]+210,272]],colors[i],2,.3+.55*act);
        txt(names[i],xs[i],657,42,colors[i],'center','serif',600);
        txt(questions[i],xs[i],717,31,P.soft);
      });
    }
    layer(sm(111.417,111.95,t),()=>{
      plane(380,464,.36,1,{time:t,flying:false,rpm:0});
      const dest=[[291,470],[472,470],[380,536]],origin=[[260,326],[500,326],[400,327]];
      for(let i=0;i<3;i++) {
        const p=sm(111.7+i*.48,112.55+i*.48,t),end=dest[i],start=origin[i];
        const a=sm(111.7+i*.48,111.9+i*.48,t);
        line([start,end],P.blue,1.5,.28*a,[5,8]);
        if(p>0&&p<1)glow(mix(start[0],end[0],p),mix(start[1],end[1],p),15,P.blue,.85);
        ring(end[0],end[1],14,P.blue,sm(.84,1,p)*.85,2);
      }
      label('机会是否相同？',380,595,P.blue,29,sm(113,113.5,t));
    });
    layer(sm(111.657,112.19,t),()=>{
      const p=sm(114.05,115.95,t),dam=sm(114.6,115.2,t);
      const x=mix(862,1050,p),y=431+dam*53;
      const path=[];
      for(let i=0;i<=28;i++) {
        const u=i/28;if(u>p)break;
        const tt=mix(114.05,115.95,u),v=sm(114.6,115.2,tt);
        path.push([mix(862,1050,u),431+v*53]);
      }
      if(path.length>1)line(path,P.red,2,.5,[6,8]);
      plane(x,y,.34,1,{time:t,heading:Math.PI/2+.16*dam,bank:.22*dam,flying:true,
        rpm:1,leftPower:1-.85*dam,rightPower:1,hit:dam,smoke:.65*dam,damage:dam});
      line([[795,561],[1125,561]],P.line,2,.6);
      label('飞行状态也会改变',960,595,P.red,29,sm(115.4,115.95,t));
    });
    layer(sm(111.897,112.43,t),()=>{
      const p=sm(116.15,117.5,t),expand=sm(117.5,118.4,t);
      const left=mix(1480,1360,expand),top=345,w=mix(250,370,expand),h=mix(188,238,expand);
      c.save();c.strokeStyle=rgba(P.gold,.62);c.lineWidth=2;c.setLineDash([8,9]);c.strokeRect(left,top,w,h);c.restore();
      documentCard(mix(1370,1513,p),366,118,150,1,true);
      documentCard(1377,437,104,127,sm(116.6,117.5,t),false);
      label('把观察范围展开',1540,615,P.gold,29,sm(117.4,118,t));
    });
    label('这三件事，都要查清',960,817,P.gold,36,sm(118.1,118.65,t));
  }

  return { history, inspect, report, roster, conditions };
};
