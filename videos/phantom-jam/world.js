(() => {
  'use strict';
  const W=1920,H=1080,TAU=Math.PI*2;
  const clamp=(v,a=0,b=1)=>Math.max(a,Math.min(b,v));
  const add=(a,b)=>a.map((x,i)=>x+b[i]);
  const sub=(a,b)=>a.map((x,i)=>x-b[i]);
  const dot=(a,b)=>a.reduce((s,x,i)=>s+x*b[i],0);
  const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
  const unit=a=>{const n=Math.hypot(...a)||1;return a.map(x=>x/n);};
  const mix=(hex,other,f)=>{
    const a=hex.replace('#',''),b=other.replace('#','');
    const c=[0,2,4].map(i=>Math.round(parseInt(a.slice(i,i+2),16)*(1-f)+parseInt(b.slice(i,i+2),16)*f));
    return `rgb(${c.join(',')})`;
  };
  let camera,queue=[],lights=[],ctx;
  function setup(c){
    const pos=[c.x,c.y,c.z],forward=unit(sub(c.target,pos));
    let right=unit(cross(forward,[0,1,0]));
    // Looking in +z should put world +x on screen right.
    right=right.map(v=>-v);
    const up=unit(cross(forward,right));
    camera={pos,forward,right,up,f:H/(2*Math.tan((c.fov||46)*Math.PI/360)),cx:c.cx??960,cy:c.cy??440};
  }
  function view(p){const d=sub(p,camera.pos);return [dot(d,camera.right),dot(d,camera.up),dot(d,camera.forward)];}
  function screen(v){return [camera.cx+camera.f*v[0]/v[2],camera.cy-camera.f*v[1]/v[2],v[2]];}
  function project(p){const v=view(p);return v[2]>.3?screen(v):null;}
  function clipped(poly){
    const out=[];
    for(let i=0;i<poly.length;i++){
      const a=poly[i],b=poly[(i+1)%poly.length],ia=a[2]>.3,ib=b[2]>.3;
      if(ia)out.push(a);
      if(ia!==ib){const k=(.30001-a[2])/(b[2]-a[2]);out.push(a.map((v,j)=>v+(b[j]-v)*k));}
    }
    return out;
  }
  function poly(points,fill,options={}){
    if(options.normal){const center=points.reduce((s,p)=>add(s,p),[0,0,0]).map(x=>x/points.length);if(dot(options.normal,sub(camera.pos,center))<=0)return;}
    const v=clipped(points.map(view));if(v.length<3)return;
    queue.push({v,fill,depth:v.reduce((s,p)=>s+p[2],0)/v.length,layer:options.layer||0,stroke:options.stroke,width:options.width||.65,alpha:options.alpha??1,blur:options.blur||0});
  }
  function line3(a,b,color,width=.04,layer=-40){
    const d=sub(b,a),n=unit([-d[2],0,d[0]]).map(v=>v*width/2);
    poly([add(a,n),add(b,n),sub(b,n),sub(a,n)],color,{layer});
  }
  function ringband(r0,r1,color,layer=-80,y=.01,start=0,end=TAU){
    const count=Math.max(6,Math.ceil((end-start)*42));
    for(let i=0;i<count;i++){
      const a=start+(end-start)*i/count,b=start+(end-start)*(i+1)/count;
      poly([[Math.sin(a)*r0,y,Math.cos(a)*r0],[Math.sin(b)*r0,y,Math.cos(b)*r0],[Math.sin(b)*r1,y,Math.cos(b)*r1],[Math.sin(a)*r1,y,Math.cos(a)*r1]],color,{layer});
    }
  }
  function flush(){
    queue.sort((a,b)=>a.layer-b.layer||b.depth-a.depth);
    for(const o of queue){
      ctx.save();ctx.globalAlpha*=o.alpha;
      ctx.beginPath();o.v.forEach((v,i)=>{const p=screen(v);i?ctx.lineTo(p[0],p[1]):ctx.moveTo(p[0],p[1]);});ctx.closePath();
      if(o.blur){ctx.shadowColor=o.fill;ctx.shadowBlur=o.blur;}
      if(Array.isArray(o.fill)){
        const ys=o.v.map(v=>screen(v)[1]),lo=Math.min(...ys),hi=Math.max(...ys);
        const g=ctx.createLinearGradient(0,lo,0,hi+1);g.addColorStop(0,o.fill[0]);g.addColorStop(.38,o.fill[1]);g.addColorStop(1,o.fill[o.fill.length-1]);ctx.fillStyle=g;
      }else ctx.fillStyle=o.fill;
      ctx.fill();
      if(o.stroke){ctx.strokeStyle=o.stroke;ctx.lineWidth=o.width;ctx.stroke();}
      ctx.restore();
    }
    for(const l of lights){
      const p=project(l.p);if(!p)continue;
      const r=clamp(camera.f*l.radius/p[2],2,38);
      const g=ctx.createRadialGradient(p[0],p[1],0,p[0],p[1],r);
      g.addColorStop(0,l.color);g.addColorStop(.18,l.color);g.addColorStop(1,'rgba(0,0,0,0)');
      ctx.save();ctx.globalCompositeOperation='screen';ctx.fillStyle=g;ctx.beginPath();ctx.arc(p[0],p[1],r,0,TAU);ctx.fill();ctx.restore();
    }
  }
  function background(){
    const g=ctx.createLinearGradient(0,0,0,H);g.addColorStop(0,'#070e19');g.addColorStop(.55,'#142736');g.addColorStop(1,'#060d16');ctx.fillStyle=g;ctx.fillRect(0,0,W,H);
    const glow=ctx.createRadialGradient(1100,300,10,1100,300,900);glow.addColorStop(0,'rgba(72,109,136,.16)');glow.addColorStop(1,'rgba(8,15,24,0)');ctx.fillStyle=glow;ctx.fillRect(0,0,W,H);
  }
  function lamp(x,z,h=7){
    const p=[x,h,z],foot=[x,0,z];
    const a=project(foot),b=project(p);if(!a||!b)return;
    // Thin roadside fixtures, whose glow remains behind the cars.
    const side=x>0?-1:1;
    const head=[x+side*.8,h,z];
    poly([[x-.055,0,z],[x+.055,0,z],[x+.055,h,z],[x-.055,h,z]],'#415360',{layer:-3});
    poly([[x,h,z-.08],[x+side*.95,h,z-.08],[x+side*.95,h,z+.08],[x,h,z+.08]],'#8a947e',{layer:-3});
    const hp=project(head);if(hp){
      const r=clamp(camera.f*2.3/hp[2],10,70),g=ctx.createRadialGradient(hp[0],hp[1],0,hp[0],hp[1],r);g.addColorStop(0,'rgba(241,204,139,.10)');g.addColorStop(1,'rgba(241,204,139,0)');ctx.fillStyle=g;ctx.fillRect(hp[0]-r,hp[1]-r,r*2,r*2);
    }
    lights.push({p:head,radius:.32,color:'rgba(251,224,177,.6)'});
    const pool=[];for(let i=0;i<24;i++){const a=i*TAU/24;pool.push([x+side*2.5+Math.cos(a)*3,.018,z+Math.sin(a)*4]);}poly(pool,'rgba(230,194,132,.035)',{layer:-60});
  }
  function road(o){
    const length=o.roadLength||130,width=o.roadWidth||8,center=o.roadCenter||0;
    poly([[-250,-.16,center-200],[250,-.16,center-200],[250,-.16,center+350],[-250,-.16,center+350]],'#0c1923',{layer:-100});
    for(let z=center-length;z<center+length;z+=12){
      poly([[-width/2,0,z],[width/2,0,z],[width/2,0,z+12],[-width/2,0,z+12]],(Math.floor(z/12)&1)?'#26343d':'#27353e',{layer:-80});
      for(const side of [-1,1]){
        poly([[side*width/2,-.10,z],[side*(width/2+.24),-.10,z],[side*(width/2+.24),.02,z+12],[side*width/2,.02,z+12]],'#44515a',{layer:-75});
        line3([side*(width/2-.28),.025,z],[side*(width/2-.28),.025,z+12],'#8a9390',.06,-55);
        for(let q=0;q<12;q+=4){const x=side*(width/2-.55);poly([[x-.025,.03,z+q],[x+.025,.03,z+q],[x+.025,.03,z+q+.25],[x-.025,.03,z+q+.25]],'#b8ad82',{layer:-50});}
      }
    }
    // Centered single lane: only shoulders, never a dashed divider that suggests a second lane.
    if(o.lamps!==false)for(let z=center-28;z<center+Math.min(length,100);z+=23)lamp(-width/2-1.9,z);
    for(let z=center-70;z<center+100;z+=8){
      for(const side of [-1,1]){const x=side*(width/2+1);poly([[x-.035,0,z],[x+.035,0,z],[x+.035,.55,z],[x-.035,.55,z]],'#526272',{layer:-4});}
    }
  }
  function ring(o){
    const r=o.ringRadius||36,w=o.roadWidth||6;
    poly([[-150,-.15,-150],[150,-.15,-150],[150,-.15,150],[-150,-.15,150]],'#0b1822',{layer:-100});
    ringband(r-w/2-.25,r+w/2+.25,'#46535b',-90,-.03);
    ringband(r-w/2,r+w/2,'#293942',-80);
    ringband(r-w/2+.22,r-w/2+.28,'#a8aa99',-60,.025);
    ringband(r+w/2-.28,r+w/2-.22,'#a8aa99',-60,.025);
    for(let a=0;a<TAU;a+=.2){
      ringband(r+w/2-.58,r+w/2-.51,'#c6b389',-55,.03,a,a+.008);
    }
    const g=[];for(let i=0;i<90;i++){const a=i*TAU/90;g.push([Math.sin(a)*(r-w/2-1),-.02,Math.cos(a)*(r-w/2-1)]);}poly(g,'#0e202b',{layer:-85});
    if(o.lamps!==false)for(let a=0;a<TAU;a+=TAU/8)lamp(Math.sin(a)*(r+w/2+3),Math.cos(a)*(r+w/2+3),5.5);
  }
  function car(c,time){
    const h=c.heading||0,co=Math.cos(h),si=Math.sin(h),scale=c.scale||1;
    const tf=p=>[c.x+scale*(p[0]*co+p[2]*si),scale*p[1],c.z+scale*(-p[0]*si+p[2]*co)];
    const normal=n=>[n[0]*co+n[2]*si,n[1],-n[0]*si+n[2]*co];
    const face=(p,color,n,extra={})=>poly(p.map(tf),color,{normal:n&&normal(n),...extra});
    const base=c.color||'#819da8',edge='rgba(198,219,226,.18)';
    const top=mix(base,'#f7e5bb',.24),side=mix(base,'#142b40',.24),front=mix(base,'#abc7d4',.09);
    const metal=[mix(base,'#c3d4dc',.15),side,mix(base,'#142b40',.48)];
    const shadow=[];for(let i=0;i<22;i++){const a=i*TAU/22;shadow.push(tf([Math.cos(a)*1.26,.025,Math.sin(a)*2.72]));}poly(shadow,'rgba(0,0,0,.46)',{layer:-5,blur:12});
    // Light is cast onto the road; brake status is a continuous scalar.
    const brake=clamp(c.brake||0),rear=dot(normal([0,0,-1]),sub(camera.pos,tf([0,.7,-2.3])))>0;
    if(brake>.03)face([[-.86,.035,-2.25],[.86,.035,-2.25],[1.4,.035,-5.6],[-1.4,.035,-5.6]],`rgba(224,57,48,${.025+brake*.065})`,null,{layer:-4});
    if(c.headlights!==false)face([[-.8,.035,2.28],[.8,.035,2.28],[2.3,.035,10],[-2.3,.035,10]],'rgba(220,225,201,.034)',null,{layer:-4});
    // Tires have actual cylindrical sidewalls, with a separate metal hub.
    for(const sx of [-1,1])for(const zz of [-1.4,1.43]){
      const xx=sx*.91,rad=.39,cy=.43;
      for(let i=0;i<12;i++){
        const a=i*TAU/12,b=(i+1)*TAU/12;
        face([[xx-.17,cy+Math.sin(a)*rad,zz+Math.cos(a)*rad],[xx+.17,cy+Math.sin(a)*rad,zz+Math.cos(a)*rad],[xx+.17,cy+Math.sin(b)*rad,zz+Math.cos(b)*rad],[xx-.17,cy+Math.sin(b)*rad,zz+Math.cos(b)*rad]],i>5?'#07111a':'#18242e',null);
      }
      const disc=[],hub=[];for(let i=0;i<16;i++){const a=i*TAU/16;disc.push([xx+sx*.18,cy+Math.sin(a)*rad,zz+Math.cos(a)*rad]);hub.push([xx+sx*.185,cy+Math.sin(a)*.23,zz+Math.cos(a)*.23]);}
      face(disc,'#0b131c',[sx,0,0]);face(hub,'#6a7d89',[sx,0,0],{stroke:'#a2adb4',width:.7});
      const phase=(c.wheelPhase??(time*(c.speed??3)))/rad;
      for(let j=0;j<5;j++){const a=j*TAU/5+phase;face([[xx+sx*.19,cy,zz],[xx+sx*.19,cy+Math.sin(a-.13)*.205,zz+Math.cos(a-.13)*.205],[xx+sx*.19,cy+Math.sin(a+.13)*.205,zz+Math.cos(a+.13)*.205]],'#253a49',[sx,0,0]);}
    }
    // Lower body has sloped front and rear corners rather than a rectangular block.
    face([[-.91,.43,-2.17],[.91,.43,-2.17],[.97,.82,-2.08],[-.97,.82,-2.08]],metal,[0,0,-1],{stroke:edge});
    face([[-.91,.43,2.17],[-.97,.82,2.08],[.97,.82,2.08],[.91,.43,2.17]],front,[0,0,1],{stroke:edge});
    for(const sx of [-1,1]){
      face([[sx*.91,.43,-2.17],[sx*.91,.43,2.17],[sx*.97,.82,2.08],[sx*.97,.94,-1.95]],metal,[sx,0,0],{stroke:edge});
      face([[sx*.97,.82,2.08],[sx*.87,1.00,1.93],[sx*.84,1.05,.75],[sx*.91,.96,-1.83],[sx*.97,.94,-1.95]],top,[sx,.6,0],{stroke:edge});
      face([[sx*.96,.52,-1.98],[sx*.96,.52,1.99],[sx*.965,.59,1.99],[sx*.965,.59,-1.98]],'#263943',[sx,0,0]);
    }
    face([[-.97,.82,2.08],[.97,.82,2.08],[.87,1,1.93],[-.87,1,1.93]],top,[0,1,1],{stroke:edge});
    face([[-.87,1,1.93],[.87,1,1.93],[.84,1.05,.75],[-.84,1.05,.75]],top,[0,1,0],{stroke:edge});
    face([[-.91,.96,-1.83],[.91,.96,-1.83],[.97,.94,-1.95],[-.97,.94,-1.95]],top,[0,1,-1],{stroke:edge});
    face([[-.91,.96,-1.83],[-.80,1,-1.52],[.80,1,-1.52],[.91,.96,-1.83]],top,[0,1,0],{stroke:edge});
    face([[-.97,.94,-1.95],[.97,.94,-1.95],[.97,.82,-2.08],[-.97,.82,-2.08]],top,[0,1,-1],{stroke:edge});
    // Sculpted cabin, two doors and blue reflective glazing.
    face([[-.84,1.05,.75],[.84,1.05,.75],[.67,1.52,.18],[-.67,1.52,.18]],'#203b4c',[0,1,1],{stroke:'#6d8997',width:.8});
    face([[-.80,1.00,-1.52],[-.67,1.52,-.68],[.67,1.52,-.68],[.80,1.00,-1.52]],'#1c3443',[0,1,-1],{stroke:'#6c8796',width:.8});
    face([[-.67,1.505,-.70],[-.24,1.505,-.70],[.62,1.04,-1.46],[.23,1.04,-1.46]],'rgba(134,172,188,.12)',[0,1,-1]);
    face([[-.80,1.075,.72],[-.54,1.075,.72],[.58,1.49,.21],[.35,1.49,.21]],'rgba(148,186,196,.09)',[0,1,1]);
    face([[-.67,1.52,-.68],[-.67,1.52,.18],[.67,1.52,.18],[.67,1.52,-.68]],top,[0,1,0],{stroke:edge});
    for(const sx of [-1,1]){
      face([[sx*.84,1.05,.75],[sx*.67,1.52,.18],[sx*.67,1.52,-.68],[sx*.80,1,-1.52]],mix(base,'#0e2534',.2),[sx,0,0],{stroke:edge});
      face([[sx*.833,1.075,.66],[sx*.686,1.46,.15],[sx*.687,1.46,-.27],[sx*.818,1.061,-.27]],'#243f4d',[sx,0,0],{stroke:'#78909a',width:.7});
      face([[sx*.818,1.055,-.37],[sx*.688,1.46,-.37],[sx*.69,1.46,-.64],[sx*.79,1.04,-1.38]],'#19333f',[sx,0,0],{stroke:'#6b8490',width:.7});
      face([[sx*.98,.88,-.14],[sx*.98,.88,.17],[sx*.98,.915,.17],[sx*.98,.915,-.14]],'#afbabd',[sx,0,0]);
      face([[sx*.98,.885,-1.15],[sx*.98,.885,-.91],[sx*.98,.915,-.91],[sx*.98,.915,-1.15]],'#9baeb3',[sx,0,0]);
      face([[sx*.974,.6,-.35],[sx*.974,.99,-.35],[sx*.974,1,-.37],[sx*.974,.6,-.37]],'#304957',[sx,0,0]);
      face([[sx*.85,1.04,.56],[sx*1.12,1.02,.49],[sx*1.13,1.13,.40],[sx*.85,1.14,.42]],top,[sx,1,0],{stroke:edge});
    }
    // Slim light bars and dark grilles create a recognizable car front and back.
    face([[-.65,.63,2.19],[.65,.63,2.19],[.65,.75,2.14],[-.65,.75,2.14]],'#102330',[0,0,1]);
    face([[-.42,.52,-2.19],[.42,.52,-2.19],[.42,.62,-2.19],[-.42,.62,-2.19]],'#344550',[0,0,-1]);
    for(const sx of [-1,1]){
      face([[sx*.48,.78,2.10],[sx*.86,.78,2.10],[sx*.85,.86,2.055],[sx*.47,.86,2.055]],'#f6e8be',[0,0,1]);
      face([[sx*.45,.76,-2.11],[sx*.87,.76,-2.11],[sx*.86,.87,-2.09],[sx*.44,.87,-2.09]],brake>.15?'#ff5a46':'#7c3438',[0,0,-1]);
      if(rear)lights.push({p:tf([sx*.68,.81,-2.12]),radius:.32+brake*.32,color:`rgba(255,73,51,${.10+brake*.7})`});
      else lights.push({p:tf([sx*.67,.82,2.11]),radius:.34,color:'rgba(255,238,193,.42)'});
    }
    if(brake>.1)face([[-.24,1.11,-1.33],[.24,1.11,-1.33],[.24,1.15,-1.27],[-.24,1.15,-1.27]],'#ff624d',[0,0,-1]);
    if(c.highlight){
      const a=[];for(let i=0;i<32;i++){const t=i*TAU/32;a.push(tf([Math.cos(t)*1.45,.04,Math.sin(t)*2.8]));}
      // A quiet road halo is distinct from red braking indicators.
      poly(a,'rgba(231,191,111,.055)',{layer:-4,stroke:'rgba(235,198,126,.35)',width:1});
    }
  }
  function markers(ms){
    for(const m of ms||[]){
      if(m.type==='band'){
        const w=m.width||8;poly([[-w/2,.05,m.z-.3],[w/2,.05,m.z-.3],[w/2,.05,m.z+.3],[-w/2,.05,m.z+.3]],m.color||'rgba(244,96,68,.3)',{layer:-3});
      } else if(m.type==='arc')ringband(m.radius-.35,m.radius+.35,m.color||'rgba(244,96,68,.5)',-3,.06,m.start,m.end);
      else if(m.type==='line')line3(m.from,m.to,m.color||'#e5bb78',m.width||.07,-3);
    }
  }
  function render(o={}){
    ctx=window.F.ctx;queue=[];lights=[];
    const defaults=o.mode==='ring'?{x:66,y:90,z:-97,target:[0,0,0],fov:45,cy:450}:{x:11,y:8,z:-13,target:[0,.4,10],fov:48,cy:435};
    setup({...defaults,...(o.camera||{})});
    ctx.save();background();o.mode==='ring'?ring(o):road(o);markers(o.markers);
    for(const c of o.cars||[])car(c,o.time||0);
    flush();
    const vignette=ctx.createRadialGradient(960,450,400,960,450,1150);vignette.addColorStop(0,'rgba(2,7,13,0)');vignette.addColorStop(1,'rgba(2,7,13,.5)');ctx.fillStyle=vignette;ctx.fillRect(0,0,W,H);
    ctx.restore();
  }
  window.World={render,project,defaults:{carLength:4.6,carWidth:1.9,carHeight:1.52},palette:['#82a9b3','#c0c3b8','#658395','#637385','#b49b72']};
})();
