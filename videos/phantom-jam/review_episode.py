"""Inspect the actual episode timeline and the exact first-impact frames."""

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from playwright.sync_api import sync_playwright
from tools import render
from tools.project import load, write_json


def main():
    folder, config, plan = load('phantom-jam')
    render.configure(ROOT, folder, config, plan)
    out = folder/config['output']/'review'
    out.mkdir(parents=True, exist_ok=True)
    moments = sorted(set([i*.5 for i in range(319)] +
                         [(s['start']+s['end'])/2 for s in plan['subtitles']] +
                         [511/30, 510/30, 512/30]))
    bounds, overlaps, impact_frames = [], [], []
    srv, url = render.server()
    try:
        with sync_playwright() as p:
            browser, page = render.browser_page(p, url)
            try:
                for t in moments:
                    boxes = page.evaluate('(t)=>window.auditBoxes(t)', t)
                    st = page.evaluate('(t)=>window.storyTime(t)', t)
                    bad = [b for b in boxes if b['x']<35 or b['y']<26 or
                           b['x']+b['w']>1885 or b['y']+b['h']>1048]
                    if bad:
                        bounds.append({'time':t, 'boxes':bad})
                    if any(a<=st<a+.65 for a in [21.6,32,45,77,94,109,123,137,146]):
                        continue
                    for i,a in enumerate(boxes):
                        for b in boxes[i+1:]:
                            dx=max(0,min(a['x']+a['w'],b['x']+b['w'])-max(a['x'],b['x']))
                            dy=max(0,min(a['y']+a['h'],b['y']+b['h'])-max(a['y'],b['y']))
                            area=min(a['w']*a['h'],b['w']*b['h'])
                            if area>0 and dx*dy/area>.20:
                                overlaps.append({'time':t,'a':a['s'],'b':b['s'],'fraction':round(dx*dy/area,3)})
                for n in [508,509,510,511,512]:
                    image=render.frame_bytes(page,n/30)
                    name=f'impact_frame_{n}.png'
                    (out/name).write_bytes(image)
                    boxes=page.evaluate('(t)=>window.auditBoxes(t)',n/30)
                    impact_frames.append({'frame':n,'sha256':hashlib.sha256(image).hexdigest(),
                                          'anchor_visible':any(b['s']==plan['anchor'] for b in boxes),'file':name})
            finally:
                browser.close()
    finally:
        srv.shutdown()
        srv.server_close()
    checks = {
        'all_sampled_text_in_bounds':not bounds,
        'three_preimpact_frames_identical':len(set(x['sha256'] for x in impact_frames[:3]))==1,
        'anchor_absent_before_511':not any(x['anchor_visible'] for x in impact_frames[:3]),
        'anchor_complete_at_511':impact_frames[3]['anchor_visible'],
        'anchor_persists_512':impact_frames[4]['anchor_visible'],
    }
    result={'source_sha256':render.source_signature(),'sample_count':len(moments),'checks':checks,
            'bounds':bounds,'text_overlap_candidates':overlaps,'impact_frames':impact_frames,
            'limits':'Text geometry does not inspect untracked decorative lettering, shape occlusion or listening quality. Image review remains necessary.'}
    write_json(out/'episode_audit.json',result)
    print(json.dumps({'sample_count':len(moments),'checks':checks,'overlap_candidates':len(overlaps)},ensure_ascii=False))
    if not all(checks.values()):
        raise SystemExit(1)


if __name__=='__main__':
    main()
