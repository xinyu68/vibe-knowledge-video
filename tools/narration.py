"""Cached paragraph synthesis and measured placement on the music timeline."""

import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import wave

import numpy as np

from .project import read_json, write_json

SR = 44100


def decode_mono(path):
    result = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-ac', '1',
                             '-ar', str(SR), '-f', 'f32le', '-'], capture_output=True, check=True)
    return np.frombuffer(result.stdout, dtype='<f4').copy()


def save_wave(path, audio):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), 'wb') as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(SR)
        stream.writeframes(np.rint(np.clip(audio, -1, 1)*32767).astype('<i2').tobytes())


def settings(folder, config, plan):
    script = (folder/config['narration']).resolve()
    if not script.is_relative_to(folder.resolve()):
        raise ValueError('narration must be inside the episode directory')
    data = read_json(script)
    if not data.get('cues'):
        raise ValueError('先在 narration.json 填写本期旁白 cues；空骨架不能合成或混音')
    if data.get('music_mode', 'constant') not in {'constant', 'duck'}:
        raise ValueError('music_mode must be constant or duck')
    previous = 0
    ids = set()
    for cue in data['cues']:
        if (not 0 <= cue['start'] < cue['end'] <= plan['duration'] or cue['start'] < previous
                or not cue.get('text') or not cue['id'].isalnum() or cue['id'] in ids):
            raise ValueError(f'Invalid or overlapping narration cue: {cue}')
        for a, b in data.get('protected_gaps', []):
            if cue['start'] < b and cue['end'] > a:
                raise ValueError(f'Narration overlaps protected music gap: {cue["id"]}')
        previous = cue['end']
        ids.add(cue['id'])
    return data


def cue_signature(data, cue):
    payload = {key: data[key] for key in ('backend', 'voice', 'rate')}
    payload['text'] = cue['text']
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def synthesize(folder, config, plan, tts_cli=None):
    data = settings(folder, config, plan)
    cli = Path(tts_cli).resolve() if tts_cli else None
    if cli is not None and not cli.is_file():
        raise FileNotFoundError('Pass the installed ttsCN scripts/tts.py with --tts-cli')

    def one(cue):
        cache = folder/'audio/narration'/cue['id']
        cache.mkdir(parents=True, exist_ok=True)
        target, meta = cache/'source.wav', cache/'source.json'
        signature = cue_signature(data, cue)
        if (target.exists() and meta.exists() and read_json(meta).get('signature') == signature
                and read_json(meta).get('sha256') == hashlib.sha256(target.read_bytes()).hexdigest()):
            print(f'{cue["id"]}: cached', flush=True)
            return
        if cli is None:
            if data['backend'] != 'edge':
                raise ValueError('The built-in backend supports edge; use --tts-cli for other configured backends')
            from .edge_voice import synthesize_edge
            details = synthesize_edge(cue['text'], target, data['voice'], data['rate'])
        else:
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'
            result = subprocess.run([sys.executable, str(cli), cue['text'], str(target),
                                     '--platform', data['backend'], '--voice', data['voice'],
                                     '--rate='+data['rate'], '--format', 'json'],
                                    capture_output=True, encoding='utf-8', env=env, timeout=150)
            if result.returncode:
                raise RuntimeError(f'TTS {cue["id"]} failed: {result.stderr[-1800:]}')
            reply = json.loads(result.stdout)
            if not reply.get('ok') or not target.is_file():
                raise RuntimeError(f'TTS returned no audio for {cue["id"]}')
            details = reply['data']
        write_json(meta, {'signature': signature, 'backend': data['backend'], 'voice': data['voice'],
                         'rate': data['rate'], 'text': cue['text'],
                         'synthesis_adapter': details.get('synthesis_adapter', 'external-cli'),
                         'edge_tts_version': details.get('edge_tts_version'),
                         'word_boundaries': details.get('word_boundaries', []),
                         'sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
        print(f'{cue["id"]}: synthesized', flush=True)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(one, data['cues']))
    return assemble(folder, config, plan)


def trim_silence(audio):
    step = round(.01*SR)
    blocks = np.pad(audio, (0, (-len(audio)) % step)).reshape(-1, step)
    rms = np.sqrt(np.mean(blocks**2, axis=1))
    active = np.flatnonzero(rms > max(10**(-52/20), float(rms.max())*10**(-42/20)))
    if not len(active):
        raise ValueError('TTS returned silence')
    start = max(0, active[0]*step-round(.08*SR))
    end = min(len(audio), (active[-1]+1)*step+round(.15*SR))
    return audio[start:end], start/SR


def assemble(folder, config, plan):
    data = settings(folder, config, plan)
    out = folder/config.get('output', 'build')
    out.mkdir(parents=True, exist_ok=True)
    track = np.zeros(round(plan['duration']*SR), dtype=np.float32)
    reports = []
    for cue in data['cues']:
        cache = folder/'audio/narration'/cue['id']
        source, meta = cache/'source.wav', cache/'source.json'
        if not source.exists() or not meta.exists():
            raise FileNotFoundError('Missing narration cache; run python vibe.py narrate <slug> first')
        metadata = read_json(meta)
        if metadata['signature'] != cue_signature(data, cue):
            raise ValueError(f'Stale TTS cache for {cue["id"]}; run narrate again')
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if digest != metadata['sha256']:
            raise ValueError(f'Changed narration audio: {cue["id"]}')
        clip, trimmed = trim_silence(decode_mono(source))
        original = len(clip)/SR
        window = cue['end']-cue['start']
        tempo = max(1., original/window)
        if tempo > data.get('max_tempo', 1.10)+1e-6:
            raise ValueError(f'{cue["id"]} needs {original:.3f}s but has {window:.3f}s; rewrite or resynthesize this sentence')
        if tempo > 1.0001:
            processed = subprocess.run(['ffmpeg', '-v', 'error', '-f', 'f32le', '-ar', str(SR), '-ac', '1',
                                        '-i', '-', '-af', f'atempo={tempo:.9f}', '-f', 'f32le', '-'],
                                       input=clip.astype('<f4').tobytes(), capture_output=True, check=True)
            clip = np.frombuffer(processed.stdout, dtype='<f4').copy()
        if len(clip) > round(window*SR):
            # atempo can retain a few milliseconds of trailing silence.
            tail = clip[round(window*SR):]
            if float(np.max(np.abs(tail))) > .003:
                raise ValueError(f'Clip would cut audible speech: {cue["id"]}')
            clip = clip[:round(window*SR)]
        fade = min(round(.008*SR), len(clip)//2)
        clip[:fade] *= np.linspace(0, 1, fade)
        clip[-fade:] *= np.linspace(1, 0, fade)
        start = round(cue['start']*SR)
        track[start:start+len(clip)] += clip
        reports.append({**cue, 'actual_end': (start+len(clip))/SR, 'trimmed_lead': trimmed,
                        'original_seconds': original, 'tempo': tempo, 'sha256': digest})
    dry = out/'narration-dry.wav'
    save_wave(dry, track)
    measure = subprocess.run(['ffmpeg', '-hide_banner', '-i', str(dry), '-af',
                              'pan=stereo|c0=c0|c1=c0,loudnorm=I=-18:TP=-2:LRA=11:print_format=json', '-f', 'null', '-'],
                             capture_output=True, encoding='utf-8', check=True).stderr
    levels = json.loads(measure[measure.rfind('{'):measure.rfind('}')+1])
    target = data.get('target_lufs', -18)
    output_voice = out/'narration.wav'
    normalization = (f'pan=stereo|c0=c0|c1=c0,loudnorm=I={target}:TP=-2:LRA=11:'
                     f'measured_I={levels["input_i"]}:measured_TP={levels["input_tp"]}:'
                     f'measured_LRA={levels["input_lra"]}:measured_thresh={levels["input_thresh"]}:'
                     f'offset={levels["target_offset"]}:linear=false,pan=mono|c0=c0')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(dry), '-af', normalization,
                    '-ar', str(SR), '-c:a', 'pcm_s16le', str(output_voice)], check=True)
    track = decode_mono(output_voice)
    if len(track) != round(plan['duration']*SR):
        raise ValueError('Loudness normalization changed the narration timeline length')
    measured = subprocess.run(['ffmpeg', '-hide_banner', '-i', str(output_voice), '-af',
                               'pan=stereo|c0=c0|c1=c0,loudnorm=I=-18:TP=-2:LRA=11:print_format=json',
                               '-f', 'null', '-'], capture_output=True, encoding='utf-8', check=True).stderr
    normalized_levels = json.loads(measured[measured.rfind('{'):measured.rfind('}')+1])
    report = {'backend': data['backend'], 'voice': data['voice'], 'rate': data['rate'],
              'duration': plan['duration'], 'normalization': 'two-pass loudnorm, stereo equivalent',
              'measured_dry': levels, 'measured_normalized': normalized_levels,
              'speech_lufs': float(normalized_levels['input_i']), 'cues': reports,
              'protected_gaps': data.get('protected_gaps', []),
              'music_mode': data.get('music_mode', 'constant'),
              'duck_db': data.get('duck_db', -11) if data.get('music_mode', 'constant') == 'duck' else 0,
              'attack': .18, 'release': .38}
    write_json(out/'narration-timing.json', report)
    print(json.dumps({'narration_cues': len(reports), 'speech_lufs': report['speech_lufs'],
                      'max_tempo': max(c['tempo'] for c in reports)}, ensure_ascii=False), flush=True)
    return track, report


def duck_envelope(length, report):
    envelope = np.ones(length, dtype=np.float32)
    if report.get('music_mode', 'duck') == 'constant':
        return envelope
    low = 10**(report['duck_db']/20)
    for cue in report['cues']:
        start = round(cue['start']*SR)
        end = min(length, round(cue['actual_end']*SR))
        attack = min(start, round(report['attack']*SR))
        release = min(length-end, round(report['release']*SR))
        if attack:
            envelope[start-attack:start] = np.minimum(envelope[start-attack:start],
                                                      np.linspace(1, low, attack))
        envelope[start:end] = np.minimum(envelope[start:end], low)
        if release:
            envelope[end:end+release] = np.minimum(envelope[end:end+release],
                                                   np.linspace(low, 1, release))
    # Preserve the music's breath and impact without a preceding duck release.
    for start, end in report.get('protected_gaps', []):
        envelope[round(start*SR):round(end*SR)] = 1
    return envelope
