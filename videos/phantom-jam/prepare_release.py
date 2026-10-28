"""Set this episode's measured preview and sound-effect schedule."""
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
def read(name): return json.loads((HERE/name).read_text(encoding='utf-8'))
def write(name,data): (HERE/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

plan=read('plan.json'); cfg=read('film.json'); knots=plan['story_knots']
def actual(s):
    for (a,x),(b,y) in zip(knots,knots[1:]):
        if x<=s<=y:return a+(b-a)*(s-x)/(y-x)
    return s

fixed=[0,.6,1.2,2.4,4,8,12,16.3,16.8,17,511/30,512/30,17.1,17.5,18,19.5,
       21.7,21.9,22.1,22.4,33.5,36,43.8,49.5,53,58,65,69.5,73,77,81,86,
       90,93.57,94.6,95.2,95.75,96.5,97.5,98,98.3,98.6,100,103.5,107,112,117,
       122,128,133,138,144,150,152,157.5]
cfg['preview_times']=sorted(set(round(t*30)/30 for t in fixed))
cfg['motion_ranges']=[[0,4,'opening'],[16.7,18,'impact'],[21.6,22.8,'impact_exit'],
  [actual(31.8),actual(32.8),'road_to_ring'],[actual(41),actual(45),'experiment_wave'],
  [49,54,'first_reaction'],[66,71,'amplification'],[78,84,'opposite_directions'],
  [93.5,96,'gold_stopping'],[96,98.8,'gold_exiting'],[98,104,'jam_remains'],
  [actual(108.8),actual(110),'density_transition'],[111,119,'density_comparison'],
  [actual(145.8),actual(147),'ending_pullback']]
cfg['review_times']=sorted(set([0,1.2,2.4,16.3,16.8,17,511/30,512/30,17.1,17.5,18,
  22.5,33.5,36,43.8,53,65,69.5,78,86,90,94.6,95.2,96.5,98.6,103.5,112,117,128,138,150,157.5]))
cfg['sfx']=[{'time':t,'kind':k,'volume':v,'duration':d} for t,k,v,d in [
  (3.02,'wind',.012,.4),(511/30,'impact',.14,.6),(32.65,'selection',.018,.3),
  (49.448,'hit',.018,.12),(68.143,'close',.023,.3),(76.48,'selection',.028,.4),(135.13,'wind',.018,.6)]]
assert len(plan['subtitles'])==41 and len(plan['narration_paragraphs'])==10
assert all((HERE/p).is_file() for p in ['world.js','traffic.js','scenes.js','research.md','storyboard.md'])
cfg['production_ready']=True
write('film.json',cfg)
print(json.dumps({'preview_frames':len(cfg['preview_times']),'motion_sequences':len(cfg['motion_ranges']),'sfx':len(cfg['sfx'])}))
