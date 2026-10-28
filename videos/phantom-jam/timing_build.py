"""Place measured paragraph narration and align bilingual captions for this episode."""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np

EPISODE = Path(__file__).resolve().parent
ROOT = EPISODE.parents[1]
sys.path.insert(0, str(ROOT))

from tools.narration import SR, assemble, decode_mono, trim_silence
from tools.project import read_json, write_json


def normalized(text):
    return ''.join(re.findall(r'[\u4e00-\u9fffA-Za-z0-9]', text))


def character_times(metadata):
    chars, spans = [], []
    for word in metadata['word_boundaries']:
        letters = normalized(word['text'])
        for index, char in enumerate(letters):
            chars.append(char)
            start = word['offset_sec'] + word['duration_sec'] * index / len(letters)
            end = word['offset_sec'] + word['duration_sec'] * (index+1) / len(letters)
            spans.append((start,end))
    return ''.join(chars), spans


def story_mapping(narration, plan):
    nominal = {'P02':18, 'P03':32, 'P04':45, 'P05':62, 'P06':77,
               'P07':94, 'P08':109, 'P09':123, 'P10':137}
    knots = [[0,0],[16.4,16.4],[511/30,511/30],[17.9,17.9]]
    knots.extend([[cue['start'],nominal[cue['id']]] for cue in narration['cues'][1:]])
    knots.extend([[narration['cues'][-1]['end'],151],[plan['duration'],plan['duration']]])
    for previous,current in zip(knots,knots[1:]):
        if current[0]<=previous[0] or current[1]<=previous[1]:
            raise ValueError('Story mapping must be strictly increasing')
    return knots


def build(mapping_only=False):
    cfg = read_json(EPISODE/'film.json')
    plan = read_json(EPISODE/'plan.json')
    narration = read_json(EPISODE/'narration.json')
    if mapping_only:
        plan['story_knots'] = story_mapping(narration,plan)
        write_json(EPISODE/'plan.json',plan)
        return
    script = read_json(EPISODE/'subtitle-script.json')
    details = {}
    for cue in narration['cues']:
        cache = EPISODE/'audio'/'narration'/cue['id']
        audio,trimmed = trim_silence(decode_mono(cache/'source.wav'))
        metadata = read_json(cache/'source.json')
        chars,spans = character_times(metadata)
        if chars != normalized(cue['text']):
            raise ValueError('Native word timestamps do not match speech: '+cue['id'])
        if normalized(''.join(s[0] for s in script[cue['id']])) != chars:
            raise ValueError('Subtitle script does not cover the paragraph: '+cue['id'])
        details[cue['id']] = {'duration':len(audio)/SR,'trimmed':trimmed,'metadata':metadata,'spans':spans}

    previous_end = 0
    for index,cue in enumerate(narration['cues']):
        cue['start'] = .2 if index==0 else 18.0 if index==1 else round(previous_end+.25,4)
        cue['end'] = round(cue['start']+details[cue['id']]['duration'],4)
        previous_end = cue['end']
    if narration['cues'][0]['end']>16.4 or not 145<=previous_end<=151.5:
        raise ValueError('Actual timing requires an editorial review before placement')

    captions,spoken_events = [],[]
    for index,cue in enumerate(narration['cues']):
        data = details[cue['id']]
        cursor = 0
        group = []
        for speech,zh,en in script[cue['id']]:
            length = len(normalized(speech))
            start = max(cue['start'],cue['start']+data['spans'][cursor][0]-data['trimmed']-.03)
            end = min(cue['end'],cue['start']+data['spans'][cursor+length-1][1]-data['trimmed'])
            group.append({'start':round(start,4),'end':round(end,4),'zh':zh,'en':en,'paragraph':cue['id']})
            spoken_events.append({'paragraph':cue['id'],'speech':speech,'start':round(start,4),'spoken_end':round(end,4)})
            cursor += length
        group[0]['start'] = cue['start']
        for i,caption in enumerate(group):
            if i+1<len(group):
                caption['end'] = group[i+1]['start']
            else:
                next_start = narration['cues'][index+1]['start'] if index+1<len(narration['cues']) else 152.0
                caption['end'] = round(min(cue['end']+.2,next_start-.04,16.4 if index==0 else 159.25),4)
        cue['subtitle'] = len(captions)+1
        cue['subtitle_end'] = len(captions)+len(group)
        captions.extend(group)

    plan['subtitles'] = captions
    plan['narration_paragraphs'] = [{'id':c['id'],'start':c['start'],'end':c['end']} for c in narration['cues']]
    plan['narration_end'] = narration['cues'][-1]['end']
    plan['story_knots'] = story_mapping(narration,plan)
    write_json(EPISODE/'narration.json',narration)
    write_json(EPISODE/'plan.json',plan)
    write_json(EPISODE/'audio'/'spoken-events.json',spoken_events)
    _,report = assemble(EPISODE,cfg,plan)

    dry = decode_mono(EPISODE/cfg.get('output','build')/'narration-dry.wav')
    voice = decode_mono(EPISODE/cfg.get('output','build')/'narration.wav')
    audible = []
    for cue in narration['cues']:
        samples = dry[round(cue['start']*SR):round(cue['end']*SR)]
        blocks = np.pad(samples,(0,(-len(samples))%441)).reshape(-1,441)
        active = np.flatnonzero(np.sqrt(np.mean(blocks**2,axis=1))>10**(-40/20))
        audible.append({'id':cue['id'],'start':round(cue['start']+active[0]*.01,4),
                        'end':round(cue['start']+(active[-1]+1)*.01,4)})
    gaps = [round(audible[i]['start']-audible[i-1]['end'],4) for i in range(1,len(audible))]
    audit = {
        'paragraphs':plan['narration_paragraphs'], 'narration_end':plan['narration_end'],
        'story_knots':plan['story_knots'], 'voice':narration['voice'], 'rate':narration['rate'],
        'max_tempo':max(c['tempo'] for c in report['cues']), 'speech_lufs':report['speech_lufs'],
        'subtitle_count':len(captions),'max_zh_chars':max(len(s['zh']) for s in captions),
        'subtitle_min_seconds':min(s['end']-s['start'] for s in captions),
        'short_captions':[s for s in captions if s['end']-s['start']<1.8],
        'voice_samples':len(voice),'expected_samples':round(plan['duration']*SR),
        'protected_region_abs_peak':float(np.max(np.abs(voice[round(16.4*SR):round(17.9*SR)]))),
        'audible_threshold_dbfs':-40,'audible_windows':audible,'audible_paragraph_gaps':gaps,
        'ordinary_gap_median':float(np.median(gaps[1:])), 'voice_subjectively_listened':False,
        'narration_sha256':hashlib.sha256((EPISODE/cfg.get('output','build')/'narration.wav').read_bytes()).hexdigest(),
        'caption_alignment':'Complete native-word transcript matched; translated captions have independent line breaks.'
    }
    assert audit['voice_samples']==audit['expected_samples'] and audit['protected_region_abs_peak']==0
    assert audit['max_tempo']<1.0001
    write_json(EPISODE/'audio'/'timing-audit.json',audit)
    print(json.dumps(audit,ensure_ascii=False,indent=2))


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mapping-only',action='store_true')
    args=parser.parse_args()
    build(args.mapping_only)
