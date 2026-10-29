(() => {
  const c = document.getElementById('stage').getContext('2d');
  let boxes = [];
  function text(s, x, y, size, english = false) {
    c.font = `${english ? 'italic ' : ''}${size}px ${english ? 'TestEnglish' : 'TestChinese'}`;
    c.textAlign = 'center';c.fillStyle = english ? '#a9bed2' : '#f0e9d8';
    c.fillText(s,x,y);
    const m=c.measureText(s);boxes.push({x:x-m.width/2,y:y-m.actualBoundingBoxAscent,w:m.width,h:m.actualBoundingBoxAscent+m.actualBoundingBoxDescent});
  }
  function draw(t) {
    boxes=[];c.fillStyle='#101d2b';c.fillRect(0,0,1920,1080);
    text('本地视频工具链 · 十秒自检',960,180,58);
    text('全新配音 / 连续动画 / 稳定混音 / 编码检查',960,260,30);
    c.strokeStyle='#3a586e';c.lineWidth=3;c.beginPath();c.moveTo(240,570);c.lineTo(1680,570);c.stroke();
    const progress=Math.min(1,Math.max(0,t/10));
    c.fillStyle=t<5?'#6eb2d1':'#dfba71';c.beginPath();c.arc(240+1440*progress,570,48,0,Math.PI*2);c.fill();
    if(t>=5&&t<6){c.strokeStyle='#dfba71';c.lineWidth=3;c.beginPath();c.arc(960,570,48+(t-5)*160,0,Math.PI*2);c.stroke();}
    text(`${Math.min(299,Math.round(t*30))} / 299`,960,730,34);
    const cue=window.FILM_PLAN.subtitles.find(s=>t>=s.start&&t<s.end);
    if(cue){text(cue.zh,960,920,44);text(cue.en,960,984,28,true);}
  }
  window.render=draw;
  window.audit=t=>{draw(t);return boxes.filter(b=>b.x<40||b.y<30||b.x+b.w>1880||b.y+b.h>1050)};
  Promise.all([document.fonts.load('44px TestChinese'),document.fonts.load('italic 28px TestEnglish')]).then(()=>{
    if(!document.fonts.check('44px TestChinese')||!document.fonts.check('italic 28px TestEnglish'))throw new Error('Self-test font loading failed');
    draw(0);window.READY=true;
  });
})();
