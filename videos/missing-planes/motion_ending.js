(() => {
'use strict';

window.MOTION_ENDING = api => {
  const {c,W,H,P,TAU,clamp,mix,sm,ease,rgba,layer,txt,tracked,line,rect,ring,plane,glow} = api;

  function polygon(points, fill, stroke=null, width=1) {
    c.beginPath();
    points.forEach((p,i)=>i?c.lineTo(...p):c.moveTo(...p));
    c.closePath();
    if(fill){c.fillStyle=fill;c.fill()}
    if(stroke){c.strokeStyle=stroke;c.lineWidth=width;c.stroke()}
  }

  function gradientRect(x,y,w,h,stops,vertical=true) {
    const g=c.createLinearGradient(x,y,vertical?x:x+w,vertical?y+h:y);
    stops.forEach(([p,col])=>g.addColorStop(p,col));
    rect(x,y,w,h,g);
  }

  function person(x,y,s=1,t=0,col='#2c3946',bag=false) {
    const walk=Math.sin(t*8.1),lift=Math.abs(walk)*1.5;
    c.save();c.translate(x,y-lift*s);c.scale(s,s);c.lineCap='round';
    c.beginPath();c.ellipse(0,0,9,10,0,0,TAU);c.fillStyle=col;c.fill();
    polygon([[-8,11],[8,11],[12,48],[-12,48]],col);
    line([[-5,44],[-6-5*walk,56],[-7-12*walk,69-Math.max(0,walk)*6]],col,7);
    line([[5,44],[6+5*walk,56],[7+12*walk,69-Math.max(0,-walk)*6]],col,7);
    line([[-7-12*walk,70-Math.max(0,walk)*6],[1-12*walk,70-Math.max(0,walk)*6]],'#aab8bc',4);
    line([[7+12*walk,70-Math.max(0,-walk)*6],[15+12*walk,70-Math.max(0,-walk)*6]],'#aab8bc',4);
    line([[-8,17],[-15+7*walk,29],[-16+12*walk,41]],col,6);
    line([[8,17],[15-7*walk,29],[16-12*walk,39]],col,6);
    if(bag)rect(11-12*walk,38,18,24,'#b5986b',null,2);
    c.restore();
  }

  function counterWorker(x,y,t) {
    const serve=sm(120.2,121.3,t)*(1-sm(122.2,123.4,t));
    c.save();c.translate(x,y);c.lineCap='round';
    c.beginPath();c.ellipse(0,0,8,9,0,0,TAU);c.fillStyle='#bfae93';c.fill();
    polygon([[-8,11],[8,11],[13,49],[-13,49]],'#485a50');
    line([[-8,17],[-21,31],[-27-serve*17,38-serve*7]],'#485a50',6);
    line([[8,17],[20,31],[12,41]],'#485a50',6);
    c.beginPath();c.arc(-27-serve*17,38-serve*7,3.5,0,TAU);c.fillStyle='#bfae93';c.fill();
    c.restore();
  }

  function storefront(cx,y,w,h,open,t,alpha=1) {
    layer(alpha,()=>{
      const x=cx-w/2;
      c.save();
      rect(x+10,y+7,w,h,'#060b11',null,4);
      gradientRect(x,y,w,h,[[0,open?'#233442':'#172330'],[1,open?'#18212a':'#101a26']]);
      line([[x,y],[x+w,y]],open?'#63717a':'#314150',2,.65);
      // The cornice, brick joints and recessed entrance give the facade depth.
      rect(x-10,y+34,w+20,18,open?'#35414a':'#202d38');
      for(let row=0;row<6;row++){
        const yy=y+92+row*47;
        line([[x+7,yy],[x+w-7,yy]],'#7c8e99',1,open?.10:.065);
        for(let q=0;q<4;q++){
          const xx=x+20+q*91+(row%2?35:0);
          if(xx<x+w-8)line([[xx,yy],[xx,yy+45]],'#7c8e99',1,.06);
        }
      }
      rect(x+22,y+56,w-44,52,open?'#604c38':'#1d2935',open?'#8f7954':'#314250',3);
      txt(open?'街角咖啡':'街角小店',cx,y+91,29,open?'#f4d9a3':'#91a5b6','center','serif',550);
      polygon([[x-9,y+124],[x+w+9,y+124],[x+w+2,y+109],[x-2,y+109]],open?'#846b49':'#304353','#4d606b');
      line([[x-9,y+124],[x+w+9,y+124]],open?'#bd9b65':'#51687a',2,.85);

      const wx=x+28,wy=y+132,ww=w-56,wh=h-160;
      rect(wx-7,wy-7,ww+14,wh+15,'#0a1018','#354652',2);
      if(open){
        glow(cx,y+h*.65,w*.65,P.gold,.13);
        // The same cafe as the opening: narrow door at left, two pendant lamps,
        // coffee cups on a dark counter, and the brown sign and awning.
        const doorW=64,winX=wx+82,winW=ww-82;
        gradientRect(winX,wy,winW,wh,[[0,'#d5b575'],[.45,'#b48c55'],[1,'#68583e']]);
        rect(wx,wy,doorW,wh,'#998257','#bca171',2);
        rect(wx+6,wy+8,doorW-12,wh*.69,'#b49e6d','#715e41',1);
        rect(wx+doorW-14,wy+wh*.62,4,24,'#e6cf9e',null,2);
        rect(winX+11,wy+39,winW-22,9,'#756340');
        for(let k=0;k<4;k++)rect(winX+20+k*47,wy+18,13,21,k%2?'#8e8d60':'#b9a770',null,2);
        for(const lx of [winX+51,winX+winW-49]){
          line([[lx,wy],[lx,wy+67]],'#5a5946',2);
          polygon([[lx-17,wy+76],[lx+17,wy+76],[lx+9,wy+63],[lx-9,wy+63]],'#5e5a40');
          glow(lx,wy+78,64,'#ffe0a2',.16);
        }
        // Lower the figure behind the foreground counter; only head and shoulders show.
        counterWorker(winX+winW*.76,wy+wh-99,t);
        rect(winX+4,wy+wh-54,winW-8,54,'#594f39');
        rect(winX+4,wy+wh-62,winW-8,10,'#3c4841');
        for(const cupX of [winX+46,winX+110]){
          rect(cupX,wy+wh-76,17,14,'#e7cf9e',null,3);
          for(let k=0;k<2;k++){
            const phase=(t*.24+k*.35)%1,pts=[];
            for(let j=0;j<6;j++)pts.push([cupX+5+k*4+Math.sin(j*.6+t+k)*3,wy+wh-80-phase*25-j*4]);
            line(pts,'#f7e3bf',1.3,Math.sin(phase*Math.PI)*.55);
          }
        }
        line([[winX+winW*.53,wy],[winX+winW*.53,wy+wh]],'#434e49',5);
        // Reflected light continues onto the pavement.
        const light=c.createLinearGradient(cx,y+h,cx,y+h+101);
        light.addColorStop(0,'rgba(227,176,94,.17)');light.addColorStop(1,'rgba(227,176,94,0)');
        polygon([[wx,y+h],[wx+ww,y+h],[wx+ww+71,y+h+100],[wx-74,y+h+100]],light);
        rect(x+w-115,y+116,96,35,'#37493f','#aaad74',2);
        txt('营业中',x+w-67,y+142,28,'#ead6a6','center','serif',550);
        const step=sm(119.4,123.7,t),door=sm(120.8,121.7,t)*(1-sm(123.2,124.3,t));
        polygon([[wx+doorW,wy],[wx+doorW-door*37,wy+door*9],[wx+doorW-door*37,wy+wh-door*7],[wx+doorW,wy+wh]],'#544e3c','#d2b783',2);
        layer(1-sm(123.0,123.7,t),()=>person(mix(cx-245,wx+33,step),mix(y+h-53,y+h-76,step),.92,t,'#7d99a8',true));
      }else{
        gradientRect(wx,wy,ww,wh,[[0,'#121b27'],[1,'#0c131d']]);
        // Empty window and a removed sign distinguish ceased trading from night closure.
        line([[wx,wy+wh*.72],[wx+ww,wy+wh*.72]],'#2c3c4d',2,.7);
        line([[wx+ww*.35,wy],[wx+ww*.35,wy+wh]],'#2c3c4d',4,.65);
        rect(wx+ww*.53,wy+wh*.62,51,45,'#1d2a37','#334656',2);
        line([[wx+ww*.53,wy+wh*.62],[wx+ww*.53+25,wy+wh*.62-13],[wx+ww*.53+51,wy+wh*.62]],'#334656',1,.7);
        rect(cx-67,wy+52,134,64,'#24323e','#64788a',2);
        txt('已停业',cx,wy+94,29,'#aab9c5','center','serif',550);
        line([[cx-30,y+119],[cx-30,wy+52]],'#617284',1,.5);
        line([[cx+30,y+119],[cx+30,wy+52]],'#617284',1,.5);
        for(let j=0;j<3;j++)line([[wx+14,wy+22+j*11],[wx+55,wy+22+j*11]],'#537086',1,.1);
      }
      rect(x-5,y+h,w+10,13,open?'#4b4c43':'#283746');
      c.restore();
    });
  }

  function shopStreet(t,zoom=1,a=1) {
    layer(a,()=>{
      c.save();
      c.translate(960,490);c.scale(zoom,zoom);c.translate(-960,-490);
      glow(960,490,520,P.gold,.075);
      // Window rectangles belong to buildings; no decorative star field.
      for(let i=0;i<7;i++){
        const x=80+i*280;
        rect(x,185+(i%3)*21,235,430,'#101a26');
        for(let k=0;k<2;k++)rect(x+40+k*100,230+(i%3)*21,42,58,'#192738','#233442',1);
      }
      line([[0,714],[1920,714]],'#475563',2,.55);
      storefront(480,300,358,398,false,t);
      storefront(960,280,358,418,true,t);
      storefront(1440,300,358,398,false,t);
      line([[115,768],[1805,768]],'#44596b',1,.18);
      c.restore();
    });
  }

  function recordCard(cx,y,open,t,a=1,index=0) {
    layer(a,()=>{
      const w=326,h=190,x=cx-w/2;
      c.save();c.shadowColor='rgba(0,0,0,.35)';c.shadowBlur=22;c.shadowOffsetY=12;
      gradientRect(x,y,w,h,[[0,'#223140'],[1,'#172330']]);c.restore();
      line([[x,y],[x+w,y]],open?P.gold:P.blue,2,.75);
      txt('经营记录',x+25,y+40,30,P.ink,'left','serif',550);
      line([[x+25,y+58],[x+w-25,y+58]],P.line,1,.6);
      const start=132.0+index*.68,row=sm(start,start+.35,t),result=sm(start+.43,start+.8,t);
      txt('采用过同类建议',x+25,y+103,28,P.soft,'left','serif',500,row);
      txt(open?'仍在营业':'已停业',x+25,y+156,31,open?P.gold:P.blue,'left','serif',550,result);
      const stamp=sm(start+.9,start+1.22,t);
      line([[x+w-61,y+139],[x+w-48,y+152],[x+w-28,y+123]],open?P.gold:P.blue,3,stamp);
      // A short baseline becomes part of the path in the next scene.
      line([[x+25,y+171],[x+w-25,y+171]],open?P.gold:P.blue,1,.35);
    });
  }

  function life(t) {
    const reveal=sm(124.846,128.7,t),records=sm(130.992,133.5,t),path=sm(137.597,138.147,t);
    const zoom=mix(1.43,1,reveal);
    // One warm storefront first, then the same unbroken street exposes absent outcomes.
    layer(1-path,()=>{
      c.save();const shrink=mix(1,.70,records);c.translate(960,mix(490,335,records));c.scale(shrink,shrink);c.translate(-960,-490);
      shopStreet(t,zoom,1);c.restore();
      txt('留下来的经验',960,155,39,P.gold,'center','serif',550,(1-sm(130.992,131.192,t))*sm(119.099,119.7,t));
      txt('把记录补完整',960,155,44,P.ink,'center','serif',550,sm(131.242,131.542,t));
      layer(reveal*(1-records),()=>{
        line([[480,782],[1440,782]],P.blue,2,.3);
        for(const x of [480,960,1440])line([[x,772],[x,794]],x===960?P.gold:P.blue,2,.7);
      });
      layer(records,()=>{
        const xs=[480,960,1440];
        xs.forEach((x,i)=>{
          const y=mix(694,586,ease(sm(131.2+i*.2,133.2+i*.2,t)));
          line([[mix(960,x,.7),483],[x,535],[x,y-8]],i===1?P.gold:P.blue,1.4,.45);
          recordCard(x,y,i===1,t,sm(131.2+i*.22,132.1+i*.22,t),i);
        });
        // Once every outcome is registered the scope can include the whole row.
        const full=sm(135.1,136.4,t);
        const left=mix(797,302,full),right=mix(1123,1618,full);
        line([[left,563],[left,552],[right,552],[right,563]],P.gold,2,.65*full);
        txt('同样做过，结果不同',960,819,32,P.gold,'center','serif',500,full);
      });
    });

    layer(path,()=>{
      // The records become an unfinished personal route through a grounded night scene.
      glow(1160,340,470,P.gold,.08);
      gradientRect(0,0,W,H,[[0,'rgba(17,30,44,0)'],[.48,'rgba(17,30,44,.04)'],[.65,'rgba(17,30,44,.18)'],[.84,'rgba(17,30,44,0)'],[1,'rgba(17,30,44,0)']]);
      polygon([[870,295],[1060,295],[1620,830],[380,830]],'#142331');
      line([[870,295],[380,830]],'#557086',2,.45);
      line([[1060,295],[1620,830]],'#557086',2,.45);
      for(let i=0;i<7;i++){
        const p=i/7,yy=325+460*p*p;
        line([[mix(860,420,p*p),yy],[mix(1080,1570,p*p),yy]],'#3a5268',1,.4);
      }
      line([[1430,710],[1430,277],[1369,277]],'#647684',6,.75);
      polygon([[1347,281],[1374,281],[1383,297],[1338,297]],'#b69d6e');
      glow(1360,305,198,P.gold,.15);
      const cone=c.createLinearGradient(1360,299,1360,730);cone.addColorStop(0,'rgba(235,191,113,.12)');cone.addColorStop(1,'rgba(235,191,113,0)');
      polygon([[1342,298],[1380,298],[1560,730],[1140,730]],cone);
      const journey=sm(137.597,142.736,t),px=mix(916,974,journey),py=mix(609,500,journey),scale=mix(1.72,1.33,journey);
      person(px,py,scale,t,'#91a8b7');
      line([[916,784],[929,752],[944,714]],P.gold,2,.6);
      const route=sm(138.1,141.5,t);
      line([[974,493],[mix(974,983,route),mix(493,372,route)]],P.gold,2,.65,[6,10]);
      // Footfalls follow the moving person, rather than a stationary silhouette sliding.
      for(let i=0;i<5;i++){
        const q=sm(138.0+i*.58,138.4+i*.58,t),fy=756-i*26,fx=927+i*8+(i%2?9:-9);
        line([[fx,fy],[fx+3,fy-9]],P.gold,4,.22*q);
      }
      txt('你的记录',420,220,45,P.ink,'left','serif',550);
      txt('仍在继续',420,276,30,P.soft,'left');
    });
  }

  function runway(t) {
    const p=sm(142.736,145.8,t);
    glow(960,330,670,P.blue,.065);
    gradientRect(0,0,W,H,[[0,'rgba(17,30,43,0)'],[.54,'rgba(17,30,43,0)'],[.69,'rgba(17,30,43,.16)'],[.86,'rgba(17,30,43,0)'],[1,'rgba(17,30,43,0)']]);
    const centers=[460,960,1460];
    centers.forEach((x,i)=>{
      const col=i===0?P.gold:P.blue;
      // Bays are marked on the airfield, not floating presentation cards.
      line([[x-180,270],[x-180,737],[x+180,737],[x+180,270]],col,2,i===0?.55:mix(.18,.7,p));
      line([[x-180,282],[x+180,282]],col,1,.23);
      line([[x,730],[x,790]],col,2,.45);
      glow(x,734,105,col,i===0?.09:mix(.02,.09,p));
      for(const dx of [-180,180]){
        rect(x+dx-3,733,6,5,col,null,1);
        glow(x+dx,736,15,col,.12);
      }
      if(i===0)plane(x,485,.61,1,{holes:1,time:t,rpm:0});
      else plane(x,485,.61,mix(.12,.48,p),{ghost:true,time:t,rpm:0});
      const register=sm(143.0+i*.85,143.65+i*.85,t);
      line([[x-44,684],[x-27,701],[x+8,663]],col,3.2,register);
      txt(i===0?'返航记录':'未返航记录',x,817,28,i===0?P.gold:P.soft,'center','serif',500,1);
    });
    txt('也给缺席者，留下位置',960,162,46,P.ink,'center','serif',550);
    line([[180,785],[1740,785]],P.line,1,.35);
  }

  function closing(t) {
    const p=sm(148.862,150.5,t),warm=sm(149.5,153.5,t);
    glow(960,454,mix(390,650,warm),P.gold,mix(.035,.12,warm));
    // Traces of two empty berths remain; light gives them a place in the judgment.
    for(const x of [330,1590]){
      line([[x-129,280],[x-129,650],[x+129,650],[x+129,280]],P.blue,1.3,mix(.35,.15,p));
      plane(x,455,.36,.25,{ghost:true,time:t,rpm:0});
      glow(x,657,86,P.gold,.06*warm);
      line([[x-129,650],[x+129,650]],P.gold,2,.65*warm);
    }
    tracked('缺席',960,532,216,40,mixColor('#b9c9d6','#efcd93',p),1);
    line([[668,607],[1252,607]],P.gold,2,.75*p);
    txt('从看不见，到放回判断',960,701,42,P.ink,'center','serif',500,p);
    txt('A PLACE IN THE WHOLE STORY',960,756,28,P.soft,'center','latin',400,p);
  }

  function mixColor(a,b,p) {
    const aa=parseInt(a.slice(1),16),bb=parseInt(b.slice(1),16);
    const rr=Math.round(mix(aa>>16,bb>>16,p)),gg=Math.round(mix((aa>>8)&255,(bb>>8)&255,p)),bl=Math.round(mix(aa&255,bb&255,p));
    return `rgb(${rr},${gg},${bl})`;
  }

  function ending(t) {
      glow(960,393,510,P.gold,.06);
      tracked('没回来的飞机',960,392,104,9,P.ink,1);
      txt('THE PLANES THAT NEVER RETURNED',960,458,28,P.soft,'center','latin',400);
      line([[668,526],[1252,526]],P.gold,1.5,.7);
      txt('幸存者偏差',960,608,36,P.gold);
      txt('研究出处：Abraham Wald · CNA 1980 重印',960,735,28,P.soft);
      txt('飞机、弹孔与飞行结果均为简化示意',960,784,28,P.soft);
  }

  return {life,runway,closing,ending};
};
})();
