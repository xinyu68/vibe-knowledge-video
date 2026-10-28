(() => {
  'use strict';
  // Illustrative IDM parameters, not fitted experimental measurements.
  const L=230,N=22,DT=.025,STEP=.1,LENGTH=4.6,T=.9,V0=14,A=.6,B=1.4,S0=2;
  const frames=[], sparse=[];
  function simulate(n,dest){
    const gap=L/n-LENGTH;
    let lo=0,hi=V0;
    for(let k=0;k<60;k++){const v=(lo+hi)/2; if(1-(v/V0)**4-((S0+v*T)/gap)**2>0)lo=v;else hi=v;}
    const x=Array.from({length:n},(_,i)=>i*L/n),v=Array(n).fill((lo+hi)/2),acc=Array(n).fill(0);
    x[0]+=.15;
    let minGap=Infinity,minSpeed=Infinity;
    for(let k=0;k<=12800;k++){
      if(k%4===0)dest.push(x.map((s,i)=>[s,v[i],acc[i]]));
      const nextV=[], nextX=[];
      for(let i=0;i<n;i++){
        const j=(i+1)%n,space=x[j]-x[i]+(j===0?L:0)-LENGTH;
        minGap=Math.min(minGap,space); minSpeed=Math.min(minSpeed,v[i]);
        const desired=S0+Math.max(0,v[i]*T+v[i]*(v[i]-v[j])/(2*Math.sqrt(A*B)));
        const a=Math.max(-5,Math.min(2,A*(1-(v[i]/V0)**4-(desired/Math.max(.01,space))**2)));
        acc[i]=a;
        if(a<0&&v[i]+a*DT<0){nextX[i]=x[i]-.5*v[i]*v[i]/a;nextV[i]=0;}
        else{nextX[i]=x[i]+v[i]*DT+.5*a*DT*DT;nextV[i]=Math.max(0,v[i]+a*DT);}
      }
      for(let i=0;i<n;i++){x[i]=nextX[i];v[i]=nextV[i];}
    }
    return {vehicles:n,circumference:L,minGap,minSpeed,frames:dest.length};
  }
  const denseAudit=simulate(N,frames),sparseAudit=simulate(14,sparse);
  const palette=['#e3d4b4','#4c8190','#b5c4c5','#254b68','#8b959a','#c8d8dc'];
  function sample(t,lowDensity=false){
    const data=lowDensity?sparse:frames, f=Math.max(0,Math.min(data.length-1.00001,t/STEP)),k=Math.floor(f),p=f-k;
    return data[k].map((a,i)=>{const b=data[k+1][i];return {id:i,s:a[0]+(b[0]-a[0])*p,v:a[1]+(b[1]-a[1])*p,a:a[2]+(b[2]-a[2])*p};});
  }
  const goldId=sample(220).reduce((best,c)=>c.v<best.v?c:best).id;
  const wrap=s=>((s+L/2)%L+L)%L-L/2;
  function cars(t,{mode='ring',center=0,lowDensity=false,gold=goldId,rotation=0}={}){
    return sample(t,lowDensity).map(c=>{
      const theta=c.s/L*Math.PI*2+rotation,R=L/(2*Math.PI);
      const point=mode==='ring'?{x:R*Math.cos(theta),z:R*Math.sin(theta),heading:-theta}:{x:0,z:wrap(c.s-center),heading:0};
      return {...point,id:c.id,color:c.id===gold?'#deb66c':palette[c.id%palette.length],brake:c.a<-.045||c.v<.5,highlight:c.id===gold,speed:c.v};
    });
  }
  function jam(t){
    const q=sample(t);let x=0,z=0,w=0;
    q.forEach(c=>{const a=c.s/L*Math.PI*2,weight=Math.max(0,5-c.v)**3;x+=Math.cos(a)*weight;z+=Math.sin(a)*weight;w+=weight;});
    return {angle:Math.atan2(z,x),strength:w,position:Math.atan2(z,x)*L/(2*Math.PI)};
  }
  // Locate a complete entry/slow/exit interval for the same gold car.
  let slow=220;
  for(let t=200;t<300;t+=.1)if(sample(t)[goldId].v<.15){slow=t;break;}
  let entry=slow,exit=slow;
  while(entry>170&&sample(entry)[goldId].v<4)entry-=.1;
  while(exit<319&&sample(exit)[goldId].v<4)exit+=.1;
  window.Traffic={sample,cars,jam,goldId,L,N,R:L/(2*Math.PI),wrap,
    passage:{entry:entry-3,slow,exit:exit+3},audit:{dense:denseAudit,sparse:sparseAudit}};
})();
