(() => {
  'use strict';
  const canvas = document.getElementById('stage');
  const ctx = canvas.getContext('2d', {alpha: false});
  const plan = window.FILM_PLAN;
  const width = 1920, height = 1080;
  let checking = false, boxes = [];
  const clamp = (v, a = 0, b = 1) => Math.max(a, Math.min(b, v));
  const smooth = (a, b, t) => { const p = clamp((t-a)/(b-a)); return p*p*(3-2*p); };
  function text(value, x, y, size = 48, color = '#edf1f5', italic = false) {
    ctx.save();
    ctx.font = `${italic ? 'italic ' : ''}500 ${size}px ${italic ? 'FilmLatin' : 'FilmSerif'}`;
    ctx.fillStyle = color; ctx.textAlign = 'center'; ctx.textBaseline = 'alphabetic';
    ctx.fillText(value, x, y);
    if (checking && ctx.globalAlpha > .4) {
      const m = ctx.measureText(value);
      boxes.push({s:value, x:x-m.width/2, y:y-m.actualBoundingBoxAscent,
        w:m.width, h:m.actualBoundingBoxAscent+m.actualBoundingBoxDescent});
    }
    ctx.restore();
  }
  function draw(t) {
    boxes = []; ctx.resetTransform(); ctx.globalAlpha = 1;
    const bg = ctx.createRadialGradient(960, 440, 0, 960, 440, 1100);
    bg.addColorStop(0, '#172e43'); bg.addColorStop(1, '#080e18');
    ctx.fillStyle = bg; ctx.fillRect(0, 0, width, height);
    // 这块占位区域应被本期具体主体与因果动作替换，不能直接作为成片。
    text(plan.title, 960, 170, 64);
    text('工程骨架 · 请按分镜编写主体动作', 960, 250, 32, '#a6b4c5');
    const impact = plan.impact_frame / plan.fps;
    if (t < impact) {
      ctx.globalAlpha = 1-smooth(impact-.63, impact-.13, t);
      ctx.strokeStyle = '#79b9de'; ctx.lineWidth = 3;
      ctx.strokeRect(680, 340, 560, 340);
      text('主体与事件待编写', 960, 530, 44, '#79b9de');
    } else {
      text(plan.anchor, 960, 560, 160, '#eac27b');
      ctx.strokeStyle = '#eac27b'; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(960, 490, 40+smooth(impact, impact+.6, t)*330, 0, Math.PI*2); ctx.stroke();
    }
    ctx.globalAlpha = 1;
    const cue = plan.subtitles.find(s => t >= s.start && t < s.end);
    if (cue) {
      text(cue.zh, 960, 930, 49);
      text(cue.en, 960, 988, 29, '#b9c5d1', true);
    }
    if (t > plan.duration-2) {
      ctx.fillStyle = `rgba(8,14,24,${smooth(plan.duration-2, plan.duration, t)})`;
      ctx.fillRect(0, 0, width, height);
    }
  }
  window.render = window.seek = t => draw(clamp(t, 0, plan.duration));
  window.audit = t => {
    checking = true; draw(t); checking = false;
    return boxes.filter(b => b.x < 40 || b.y < 28 || b.x+b.w > width-40 || b.y+b.h > height-36);
  };
  window.READY = false;
  Promise.all([document.fonts.load('500 49px FilmSerif', '知识视频'),
    document.fonts.load('italic 500 29px FilmLatin', 'Knowledge')]).then(() => {
      draw(0); window.READY = true;
    }).catch(error => { console.error(error); });
})();
