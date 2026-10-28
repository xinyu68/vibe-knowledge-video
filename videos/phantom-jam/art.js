(() => {
  'use strict';
  const ctx = document.getElementById('stage').getContext('2d', {alpha:false});
  const W=1920, H=1080;
  const clamp=(v,a=0,b=1)=>Math.max(a,Math.min(b,v));
  const lerp=(a,b,p)=>a+(b-a)*p;
  const smooth=(a,b,t)=>{const p=clamp((t-a)/(b-a)); return p*p*(3-2*p);};
  const F={ctx,W,H,clamp,lerp,smooth,checking:false,boxes:[]};
  F.text=(value,x,y,size=48,color='#eef1f5',options={})=>{
    ctx.save();
    const o=options||{};
    ctx.globalAlpha*=o.alpha===undefined?1:o.alpha;
    ctx.font=`${o.italic?'italic ':''}${o.weight||500} ${size}px ${o.italic?'FilmLatin':'FilmSerif'}`;
    if(o.maxWidth){const w=ctx.measureText(value).width;if(w>o.maxWidth){size*=o.maxWidth/w;ctx.font=`${o.italic?'italic ':''}${o.weight||500} ${size}px ${o.italic?'FilmLatin':'FilmSerif'}`;}}
    ctx.textAlign=o.align||'center'; ctx.textBaseline='alphabetic';
    ctx.fillStyle=color;
    if(o.shadow){ctx.shadowColor='rgba(0,0,0,.7)';ctx.shadowBlur=9;ctx.shadowOffsetY=2;}
    ctx.fillText(value,x,y);
    if(F.checking&&ctx.globalAlpha>.4){
      const m=ctx.measureText(value),tr=ctx.getTransform();
      const left=x-(ctx.textAlign==='center'?m.width/2:ctx.textAlign==='right'?m.width:0);
      const top=y-m.actualBoundingBoxAscent;
      const corners=[[left,top],[left+m.width,top],[left, y+m.actualBoundingBoxDescent],[left+m.width,y+m.actualBoundingBoxDescent]].map(p=>[tr.a*p[0]+tr.c*p[1]+tr.e,tr.b*p[0]+tr.d*p[1]+tr.f]);
      const xs=corners.map(p=>p[0]),ys=corners.map(p=>p[1]);
      F.boxes.push({s:value,x:Math.min(...xs),y:Math.min(...ys),w:Math.max(...xs)-Math.min(...xs),h:Math.max(...ys)-Math.min(...ys),role:o.role||'scene'});
    }
    ctx.restore();
  };
  F.line=(points,color='#eac27b',width=2)=>{
    ctx.save();ctx.strokeStyle=color;ctx.lineWidth=width;ctx.lineCap='round';ctx.lineJoin='round';ctx.beginPath();points.forEach((p,i)=>i?ctx.lineTo(p[0],p[1]):ctx.moveTo(p[0],p[1]));ctx.stroke();ctx.restore();
  };
  F.roundRect=(x,y,w,h,r=12,fill,stroke,width=1)=>{
    ctx.save();ctx.beginPath();ctx.roundRect(x,y,w,h,r);if(fill){ctx.fillStyle=fill;ctx.fill();}if(stroke){ctx.strokeStyle=stroke;ctx.lineWidth=width;ctx.stroke();}ctx.restore();
  };
  window.F=F;
})();
