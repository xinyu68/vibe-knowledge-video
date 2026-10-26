(() => {
'use strict';

// Each scene is a pure function of the absolute film time.
window.MOTION_OPENING = api => {
  const {c,W,H,P,TAU,T,clamp,mix,sm,ease,rgba,layer,txt,tracked,line,rect,ring,plane,glow,shape} = api;
  const cloudSeeds = [
    [-120,275,400,105,.30],[340,206,355,87,.22],[820,166,360,92,.16],
    [1430,190,365,104,.25],[1900,320,440,127,.36],[-110,640,410,147,.33],
    [360,745,370,88,.18],[1320,746,420,104,.23],[1860,700,420,155,.36]
  ];

  function ellipse(x,y,rx,ry,color,alpha=1){
    if(alpha<=0)return;
    c.save();c.globalAlpha*=alpha;c.beginPath();c.ellipse(x,y,rx,ry,0,0,TAU);c.fillStyle=color;c.fill();c.restore();
  }

  function fog(x,y,rx,ry,alpha,color='#91afbf'){
    c.save();c.translate(x,y);c.scale(rx,ry);
    const g=c.createRadialGradient(0,0,.04,0,0,1);
    g.addColorStop(0,rgba(color,alpha));g.addColorStop(.45,rgba(color,alpha*.48));g.addColorStop(1,rgba(color,0));
    c.fillStyle=g;c.fillRect(-1,-1,2,2);c.restore();
  }

  function atmosphere(t,strength=1){
    const g=c.createLinearGradient(0,0,0,H);
    g.addColorStop(0,'#0a1725');g.addColorStop(.19,'#172c40');g.addColorStop(.58,'#0b1a2b');g.addColorStop(1,'#07101b');
    layer(strength,()=>{c.fillStyle=g;c.fillRect(0,0,W,H)});
    cloudSeeds.forEach(([x,y,rx,ry,a],i)=>{
      const drift=(t*.012+i*.17);
      fog(x+Math.sin(drift)*37,y+Math.cos(drift*.7)*13,rx,ry,a*strength);
    });
  }

  function lamp(x,y,r=3,alpha=1){
    glow(x,y,r*7,P.gold,.17*alpha);
    ellipse(x,y,r,r*.7,'#ffe3a4',alpha);
  }

  function runway(t,alpha=1){
    layer(alpha,()=>{
      c.save();c.translate(960,460);c.rotate(-.09);
      const road=c.createLinearGradient(-240,0,240,0);
      road.addColorStop(0,'#121e27');road.addColorStop(.48,'#27323b');road.addColorStop(1,'#121e27');
      shape(c,[[-110,-360],[110,-360],[260,410],[-260,410]],road,null);
      line([[-110,-360],[-260,410]],'#8a9d9f',2,.22);
      line([[110,-360],[260,410]],'#8a9d9f',2,.22);
      for(let i=0;i<10;i++){
        const yy=-350+i*80+(t*19)%80,q=(yy+360)/770,xx=110+150*q;
        lamp(-xx-11,yy,2.5+q*1.3,.5+q*.5);lamp(xx+11,yy,2.5+q*1.3,.5+q*.5);
        line([[0,yy],[0,yy+20+q*13]],'#c6c5ac',3+q*2,.2);
      }
      c.restore();
    });
  }

  function beam(x,y,width,height,color,alpha){
    c.save();const g=c.createLinearGradient(x,y,x,y+height);
    g.addColorStop(0,rgba(color,alpha));g.addColorStop(1,rgba(color,0));
    shape(c,[[x-13,y],[x+13,y],[x+width/2,y+height],[x-width/2,y+height]],g,null);c.restore();
  }

  function airShadow(x,y,s,alpha=.3){
    fog(x+25,y+40,360*s,125*s,alpha,'#000408');
  }

  function intro(t){
    const p=sm(0,4.2,t),recover=sm(1.05,3.55,t);
    const instability=(1-recover),bank=.55*Math.sin(t*5.3+.9)*instability+.035*Math.sin(t*2);
    atmosphere(t,1);
    runway(t*2.7,.25+.35*p);
    // A damaged engine sputters, the wings correct their bank, then the aircraft stabilises.
    const x=960+Math.sin(t*3.1)*29*instability,y=mix(495,432,p),s=mix(1.25,1.17,p);
    const heading=-.07+Math.sin(t*3.3)*.075*instability;
    airShadow(x,y,s,.55);
    glow(x-245,y-70,280,P.blue,.09);
    plane(x,y,s,1,{holes:1,time:t,heading,bank,flying:true,rpm:1,
      leftPower:mix(.22,.62,recover),rightPower:1,smoke:mix(.96,.30,recover),smokeSide:-1,damage:.82});
    c.save();c.translate(x,y);c.rotate(heading);c.scale(s,s);
    // Navigation lamps belong to the aircraft rather than floating UI decoration.
    glow(-321,37,29,P.red,.31);ellipse(-321,37,3.6,2.7,'#ffc9b4');
    glow(321,37,26,P.olive,.22);ellipse(321,37,3.4,2.5,'#c6ffff');
    const sputter=(.5+.5*Math.sin(t*21))*(1-recover);
    glow(-95,-42,43,P.red,.26*sputter);
    for(let j=0;j<5;j++){
      const age=(t*1.9+j*.19)%1;
      ellipse(-95+Math.sin(j*2.1)*8*age,-31+age*66,1.6*(1-age)+.4,2.7*(1-age)+.4,'#f8c187',(1-age)*.8*sputter);
    }
    c.restore();
    // Very low cloud crosses only an outer wing. The principal silhouette remains clear.
    fog(1390-130*p,642+20*p,430,85,.30,'#9ab5c7');
    fog(325-65*p,505+14*p,315,140,.18,'#b7c4cc');
    line([[140,174],[258,174]],P.gold,2,.68);
    txt('返航途中',140,147,32,'#f1cf8b','left','serif',500,1);
    txt('它还能回来吗？',144,222,40,P.ink,'left','serif',550,sm(.18,.65,t));
    txt('受损，不等于坠落',1470,733,32,P.gold,'center','serif',500,sm(2.7,3.25,t));
  }

  function storeWall(x,w,alive){
    const y=265,h=492;
    // Dimensional cornice, masonry face, recessed glass and a projecting awning.
    const wall=c.createLinearGradient(x,y,x+w,y+h);
    wall.addColorStop(0,alive?'#3c484d':'#263b4a');
    wall.addColorStop(1,alive?'#1d2b32':'#142431');
    rect(x,y,w,h,wall,'#3e5565',4);
    shape(c,[[x-12,y-14],[x+w+12,y-14],[x+w,y],[x,y]],alive?'#62625b':'#405060',null);
    rect(x-12,y-22,w+24,12,alive?'#8c8772':'#536475');
    for(let yy=y+125;yy<y+h;yy+=45)line([[x+9,yy],[x+w-9,yy]],'#8b9e9f',1,.06);
    rect(x+22,y+97,w-44,h-120,alive?'#0d2028':'#0c1a25','#536371',5);
    rect(x+10,y+24,w-20,58,alive?'#604c38':'#263440',alive?'#8f7954':'#3b5060',3);
    txt(alive?'街角咖啡':'街角小店',x+w/2,y+65,34,alive?'#f4d9a3':'#9bafbf','center','serif',550);
    shape(c,[[x-16,y+110],[x+w+16,y+110],[x+w+2,y+88],[x-2,y+88]],alive?'#846b49':'#304353','#4d606b',1);
    line([[x-16,y+111],[x+w+16,y+111]],alive?'#bd9b65':'#51687a',3,.8);
    rect(x-6,y+h-7,w+12,14,alive?'#536168':'#3a4f5e');
    return {x,y,w,h};
  }

  function person(x,y,s,col,alpha=1,walk=0){
    layer(alpha,()=>{
      c.save();c.translate(x,y-Math.abs(walk)*2);c.scale(s,s);
      ellipse(0,-63,9,11,'#bdac99');
      c.lineCap='round';
      line([[0,-49],[0,-17]],col,23);
      line([[-7,-15],[-7-7*walk,0],[-10-17*walk,17-Math.max(0,walk)*5]],'#172b36',8);
      line([[7,-15],[7+7*walk,0],[9+17*walk,17-Math.max(0,-walk)*5]],'#20333e',8);
      line([[-10-17*walk,18-Math.max(0,walk)*5],[-1-17*walk,18-Math.max(0,walk)*5]],'#8e9f9f',5);
      line([[9+17*walk,18-Math.max(0,-walk)*5],[18+17*walk,18-Math.max(0,-walk)*5]],'#8e9f9f',5);
      line([[-9,-43],[-17+12*walk,-28],[-19+18*walk,-16]],col,7);
      line([[10,-43],[16-12*walk,-29],[19-18*walk,-18]],col,7);
      c.restore();
    });
  }

  function barista(x,y,t){
    const pour=sm(4.8,5.5,t)*(1-sm(6.5,7.2,t));
    const serve=sm(7.1,8.2,t);
    c.save();c.translate(x+serve*10,y);c.lineCap='round';
    ellipse(0,0,10,11,'#bda98d');
    line([[0,16],[0,58]],'#485a50',25);
    const handX=mix(-22,-43,pour),handY=mix(37,19,pour);
    line([[-8,18],[-24,31],[handX,handY]],'#485a50',8);
    ellipse(handX,handY,4,4,'#bda98d');
    line([[8,18],[24,34],[10+serve*23,44]],'#485a50',8);
    c.save();c.translate(handX-5,handY-4);c.rotate(-pour*.55);
    rect(-9,-12,17,23,'#d2c6a4','#706e5b',3);
    c.restore();
    if(pour>.15)line([[handX-13,handY-6],[-55,43]],'#ecd1a0',2.1,.8*pour);
    c.restore();
  }

  function steam(x,y,t,alpha=.5){
    for(let k=0;k<3;k++){
      const phase=(t*.28+k*.31)%1;
      const a=Math.sin(phase*Math.PI)*alpha;
      const pts=[];for(let j=0;j<8;j++){
        const yy=y-phase*45-j*5;
        pts.push([x+k*7+Math.sin(j*.55+t*1.4+k)*4,yy]);
      }
      line(pts,'#f7e3bf',1.6,a);
    }
  }

  function shop(t){
    const p=sm(4.2,8.4,t);
    const street=c.createLinearGradient(0,0,0,H);
    street.addColorStop(0,'#0a1828');street.addColorStop(.22,'#11283d');street.addColorStop(.63,'#0c1c2a');street.addColorStop(.78,'#12232e');street.addColorStop(1,'#07111c');
    c.fillStyle=street;c.fillRect(0,0,W,H);
    // Quiet upper floors establish that these are occupied buildings on one street.
    for(let i=0;i<8;i++){
      const xx=105+i*237;
      rect(xx,140,178,92,'#183244','#294658');
      rect(xx+18,154,63,62,i===4?'#6f6749':'#1f3b4d');
      rect(xx+96,154,63,62,i===6?'#485144':'#203b4d');
    }
    const dead=storeWall(250,515,false),live=storeWall(902,690,true);
    // Failure is a specific long-term state, not a shop that merely closed for the night.
    for(let j=0;j<8;j++)line([[dead.x+28,dead.y+130+j*39],[dead.x+dead.w-28,dead.y+130+j*39]],'#486071',2,.58);
    rect(dead.x+156,dead.y+227,205,98,'#172b39','#627483',3);
    txt('已停业',dead.x+258,dead.y+289,39,'#9cabb5','center','serif',550);
    line([[dead.x+70,dead.y+442],[dead.x+185,dead.y+442]],'#405867',3,.7);
    rect(dead.x+60,dead.y+404,50,37,'#213947','#385364',1);
    shape(c,[[dead.x+110,dead.y+404],[dead.x+129,dead.y+413],[dead.x+129,dead.y+442],[dead.x+110,dead.y+441]],'#182c3a','#385364');

    const wx=live.x+167,wy=live.y+122,ww=live.w-197,wh=330;
    const windowLight=c.createLinearGradient(wx,wy,wx+ww,wy+wh);
    windowLight.addColorStop(0,'#d5b575');windowLight.addColorStop(.45,'#b48c55');windowLight.addColorStop(1,'#68583e');
    glow(live.x+live.w/2,570,365,P.gold,.12);
    rect(wx,wy,ww,wh,windowLight,'#c6a46f',2);
    rect(wx+22,wy+39,ww-44,15,'#756340');
    for(let i=0;i<7;i++){
      const bx=wx+35+i*61;
      rect(bx,wy+12,17,27,i%2?'#8e8d60':'#b9a770',null,3);
    }
    line([[wx+ww*.53,wy],[wx+ww*.53,wy+wh]],'#434e49',7);
    // Pendant lights and activity make the bright store a place, not a colored rectangle.
    [wx+120,wx+365].forEach(lx=>{
      line([[lx,wy],[lx,wy+63]],'#5a5946',2);
      shape(c,[[lx-21,wy+72],[lx+21,wy+72],[lx+10,wy+57],[lx-10,wy+57]],'#5e5a40',null);
      lamp(lx,wy+74,4,.95);beam(lx,wy+74,110,172,P.gold,.17);
    });
    barista(wx+245,wy+183,t);
    rect(wx+10,wy+244,ww-20,13,'#3c4841');
    rect(wx+10,wy+257,ww-20,73,'#594f39');
    rect(wx+84,wy+229,20,15,'#e7cf9e',null,3);steam(wx+90,wy+224,t,.65);
    rect(wx+190,wy+226,24,18,'#d7be8b',null,3);steam(wx+201,wy+218,t+.6,.5);
    // A narrow entrance with a warm light spill and a customer approaching it.
    const dx=live.x+28,dy=live.y+122;
    rect(dx,dy,113,330,'#998257','#bca171',2);
    rect(dx+7,dy+8,99,220,'#b49e6d','#715e41',1);
    shape(c,[[dx,dy+331],[dx+112,dy+331],[dx+212,840],[dx-112,840]],rgba(P.gold,.12),null);
    const door=sm(5.4,6.4,t)*(1-sm(7.5,8.4,t));
    shape(c,[[dx+112,dy],[dx+112-67*door,dy+20*door],[dx+112-67*door,dy+330-16*door],[dx+112,dy+330]],'#544e3c','#d2b783',2);
    const enter=sm(4.35,7.05,t),px=mix(765,dx+65,enter),py=mix(775,741,enter);
    person(px,py,mix(1.04,.9,enter),'#71959e',1-sm(6.9,7.3,t),Math.sin((t-4.2)*9)*.95*(1-sm(6.6,7.0,t)));
    glow(live.x+live.w/2,792,260,P.gold,.08);
    line([[125,789],[1795,789]],'#78909c',2,.32);
    line([[85,835],[1815,835]],'#294451',2,.55);
    txt('营业中',live.x+live.w/2,live.y-43,32,P.gold,'center','serif',550);
    fog(1750,365,285,270,.1,'#7295a9');
  }

  function berth(x,y,w,h,alpha=1,warm=false){
    layer(alpha,()=>{
      const fl=c.createLinearGradient(x-w/2,y-h/2,x+w/2,y+h/2);
      fl.addColorStop(0,warm?'#28373c':'#142533');fl.addColorStop(1,warm?'#14242f':'#0c1925');
      rect(x-w/2,y-h/2,w,h,fl,null,6);
      line([[x-w/2+20,y-h/2+17],[x-w/2+20,y+h/2-17],[x+w/2-20,y+h/2-17],[x+w/2-20,y-h/2+17]],warm?'#899b9c':'#4b667a',2.5,.64);
      line([[x-w*.22,y-h/2+25],[x+w*.22,y-h/2+25]],warm?'#899b9c':'#4b667a',2,.5);
      for(const side of [-1,1]){
        if(warm)lamp(x+side*(w/2-20),y+h/2-16,4,.8);
        else ellipse(x+side*(w/2-20),y+h/2-16,3,2,'#526b7e',.7);
      }
    });
  }

  function hook(t){
    const pull=sm(12.9,14.7,t),x=mix(925,595,pull),y=mix(465,477,pull),s=mix(1.34,.83,pull);
    const ambience=c.createRadialGradient(960,410,170,960,490,1000);
    ambience.addColorStop(0,'#1b3447');ambience.addColorStop(.6,'#0c1c2a');ambience.addColorStop(1,'#07111d');
    c.fillStyle=ambience;c.fillRect(0,0,W,H);
    // Hangar pools of light reveal scale without a heavy dashboard frame.
    beam(780,99,1150,730,P.blue,.075*(1-pull));
    layer(pull,()=>{
      berth(595,480,545,570,1,true);berth(1305,480,545,570,1,false);
      beam(594,111,580,660,P.gold,.10);beam(1305,111,490,660,P.blue,.025);
      line([[1305,288],[1305,660]],'#416075',2,.23,[9,15]);
      line([[1207,550],[1250,550]],'#567082',5,.5);line([[1360,550],[1403,550]],'#567082',5,.5);
      txt('已返航',595,196,34,P.gold,'center','serif',550);
      txt('未归的机位',1305,196,34,P.soft,'center','serif',500);
      txt('它们的伤口在哪里？',1305,807,32,P.red,'center','serif',500,sm(13.3,14.3,t));
    });
    airShadow(x,y,s,.5);
    const scan=sm(8.7,11.7,t);
    plane(x,y,s,1,{holes:1,time:t,rpm:mix(.32,0,sm(8.4,9.5,t)),scan:t<11.75?scan:undefined});
    // Inspection traces are written one after another; they are the records we can see.
    layer((1-pull)*sm(9.1,9.6,t),()=>{
      const targets=[[-224,9],[160,-11],[247,25]];
      targets.forEach(([hx,hy],i)=>{
        const progress=sm(9.25+i*.62,9.75+i*.62,t);
        const xx=1502,yy=288+i*65;
        const from=[x+hx*s,y+hy*s],to=[xx-28,yy-10];
        const q=sm(9.25+i*.62,9.67+i*.62,t);
        line([from,[mix(from[0],to[0],q),mix(from[1],to[1],q)]],P.red,1.2,.26*progress);
        txt('弹孔记录',xx,yy,30,P.soft,'left','serif',500,progress);
        line([[xx-20,yy-11],[xx-14,yy-4],[xx-3,yy-19]],P.gold,2.6,progress);
      });
    });
    layer(1-pull,()=>{
      txt('你看见了伤口',142,196,42,P.ink,'left','serif',550);
      const holes=[[-224,9],[160,-11],[247,25]];
      holes.forEach(([hx,hy],i)=>{
        const appear=sm(8.65+i*.45,9.3+i*.45,t),rx=x+hx*s,ry=y+hy*s;
        ring(rx,ry,14,P.red,.58*appear,1.4);glow(rx,ry,21,P.red,.10*appear);
      });
      txt('返航者的伤痕',1485,579,32,'#f1a48c','center','serif',500,sm(10.7,11.2,t));
    });
    // Tiny optical glints make metal react to the moving light, not to arbitrary bouncing.
    const glint=sm(8.5,10,t)*(1-sm(11.0,12.1,t));
    line([[x-315*s,y+29*s],[x-145*s,y-12*s]],'#c0e0e8',2,.24*glint*(1-pull));
    fog(1785,640,300,140,.1,'#738f9f');
  }

  function anchor(t){
    const u=Math.max(0,t-T),pulse=Math.exp(-u*4.1),out=1-sm(21.35,22.1,t);
    layer(out,()=>{
      // On frame 511, the light and the word arrive together at full legibility.
      const wash=c.createRadialGradient(960,465,60,960,465,1000);
      wash.addColorStop(0,rgba('#d9bd7d',.19+.28*pulse));
      wash.addColorStop(.45,rgba('#4a6a76',.09+.13*pulse));
      wash.addColorStop(1,rgba('#08111d',0));
      c.fillStyle=wash;c.fillRect(0,0,W,H);
      const q=clamp(u/1.05),radius=95+680*ease(q);
      if(q<1){ring(960,450,radius,P.gold,(1-q)*.46,2.1);ring(960,450,radius-11,P.blue,(1-q)*.15,1.1);}
      fog(960,470,570,390,.11+.14*pulse,'#e8c88c');
      // Vacant places stay visible in the surrounding darkness, giving the word a subject.
      berth(283,453,270,425,.27,false);berth(1637,453,270,425,.27,false);
      c.save();c.shadowColor=rgba(P.gold,.2+.25*pulse);c.shadowBlur=20+25*pulse;
      tracked('缺席',960,548,276,56,'#f7e7c4',1);
      c.restore();
      const a=sm(T+.6,T+.95,t);
      line([[690,613],[1230,613]],P.gold,2,.7*a);
      txt('幸存者偏差',960,687,42,P.ink,'center','serif',500,a);
      txt('SURVIVORSHIP BIAS',960,741,28,P.soft,'center','latin',400,a);
      txt('看见留下来的，也看见没有回来的。',960,814,28,P.soft,'center','serif',400,sm(T+1.6,T+2.3,t));
    });
  }

  return {intro,shop,hook,anchor};
};
})();
