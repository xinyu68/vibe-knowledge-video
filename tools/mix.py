import hashlib
import json
import subprocess
import wave

import numpy as np

from .project import music_path, project_reference, write_json

SR = 44100


def smooth_noise(rng, n, width=16):
    values = rng.standard_normal(n + width).astype(np.float32)
    cumulative = np.concatenate((np.zeros(1, dtype=np.float32), np.cumsum(values, dtype=np.float32)))
    return (cumulative[width:] - cumulative[:-width])[:n] / np.sqrt(width)


def decode(path, channels=2):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-map', '0:a:0', '-vn',
                          '-ac', str(channels), '-ar', str(SR), '-f', 'f32le', '-'],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype='<f4').reshape(-1, channels).copy()


def effect(rng, kind, duration):
    length = round(duration * SR)
    t = np.arange(length) / SR
    if kind == 'impact':
        phase = 2 * np.pi * (44*t + 44*.13*(1-np.exp(-t/.13)))
        sound = np.sin(phase)*np.exp(-t/.19)*np.minimum(t/.006, 1)
        sound += smooth_noise(rng, length, 35)*np.exp(-t/.045)*np.minimum(t/.003, 1)*.12
    elif kind == 'close':
        sound = (np.sin(2*np.pi*220*t)+.25*np.sin(2*np.pi*440*t))*np.exp(-t/.35)*np.minimum(t/.012, 1)
    elif kind == 'plate':
        sound = (np.sin(2*np.pi*340*t)+.35*np.sin(2*np.pi*681*t))*np.exp(-t/.045)*np.minimum(t/.003, 1)
        sound += smooth_noise(rng, length, 8)*.16*np.exp(-t/.025)
    elif kind == 'hit':
        sound = np.sin(2*np.pi*145*t)*np.exp(-t/.04)*np.minimum(t/.003, 1)
        sound += smooth_noise(rng, length, 18)*.25*np.exp(-t/.025)
    elif kind == 'engine_loss':
        phase = 2*np.pi*(30*t+42*.22*(1-np.exp(-t/.22)))
        sound = (np.sin(phase)*.68+smooth_noise(rng, length, 65)*.18)*np.sin(np.pi*t/duration)**2
    elif kind == 'scan':
        sound = (smooth_noise(rng, length, 15)*.55+.15*np.sin(2*np.pi*(530*t+500*t*t)))*np.sin(np.pi*t/duration)**2
    elif kind in {'selection', 'wind', 'paper'}:
        sound = smooth_noise(rng, length, 7 if kind == 'paper' else 70)*np.sin(np.pi*t/duration)**2
    else:
        raise ValueError(f'未知音效: {kind}')
    return sound / max(1, float(np.max(np.abs(sound))))


def mix(folder, config, plan):
    music = music_path(folder, config)
    bg = decode(music)
    duration = len(bg) / SR
    if abs(duration - plan['duration']) > 1 / 30:
        raise ValueError(f'音乐实际解码为 {duration:.6f} 秒，plan.json 为 {plan["duration"]} 秒；先重做时间轴')
    source_duration = duration
    expected_samples = round(plan['duration'] * SR)
    alignment_samples = expected_samples - len(bg)
    if alignment_samples > 0:
        bg = np.pad(bg, ((0, alignment_samples), (0, 0)))
    elif alignment_samples < 0:
        bg = bg[:expected_samples]
    duration = len(bg) / SR
    audio = bg * np.float32(10**(config.get('music_gain_db', -6)/20))
    n = len(audio)
    narration = None
    narration_report = None
    music_envelope = np.ones(n, dtype=np.float32)
    if config.get('narration'):
        from .narration import assemble, duck_envelope
        narration, narration_report = assemble(folder, config, plan)
        music_envelope = duck_envelope(n, narration_report)
        audio *= music_envelope[:, None]
    rng = np.random.default_rng(73018)
    env = np.minimum(1, np.arange(n)/(SR*2))*np.minimum(1, (n-1-np.arange(n))/(SR*3))
    ambience = smooth_noise(rng, n, 130)*env*config.get('ambience_gain', .0008)
    audio[:, 0] += ambience
    audio[:, 1] += ambience*.85
    bed = config.get('engine_bed')
    if bed:
        start, end = bed
        if not 0 <= start < end <= duration:
            raise ValueError('engine_bed 不在音轨范围内')
        length = round((end-start)*SR)
        t = np.arange(length)/SR
        envelope = np.minimum(1, t/.18)*np.minimum(1, (end-start-t)/.55)
        engine = (.6*np.sin(2*np.pi*68*t)+.24*np.sin(2*np.pi*137*t)+smooth_noise(rng, length, 80)*.24)
        engine *= envelope*(.011+.003*np.sin(t*9)**2)
        offset = round(start*SR)
        length = min(length, n-offset)
        audio[offset:offset+length, 0] += engine[:length]
        audio[offset:offset+length, 1] += engine[:length]*.9
    for event in config.get('sfx', []):
        sound = np.asarray(effect(rng, event['kind'], event['duration'])*event['volume'], dtype=np.float32)
        a = round(event['time']*SR)
        b = min(n, a+len(sound))
        audio[a:b, 0] += sound[:b-a]
        audio[a:b, 1] += sound[:b-a]*.92
    if narration is not None:
        if len(narration) != n:
            raise ValueError('Narration sample count differs from the planned timeline; rebuild narration')
        audio += narration[:, None]
    fade = min(n, round(.06*SR))
    audio[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)[:, None]
    peak = float(np.max(np.abs(audio)))
    attenuation = min(1, .83/max(peak, 1e-10))
    audio *= attenuation
    out = folder / config.get('output', 'build')
    out.mkdir(parents=True, exist_ok=True)
    target = out / 'soundtrack.wav'
    with wave.open(str(target), 'wb') as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(SR)
        wav.writeframes(np.rint(np.clip(audio, -1, 1)*32767).astype('<i2').tobytes())
    metadata = {'music': project_reference(music), 'paths_relative_to': 'project_root',
                'music_sha256': hashlib.sha256(music.read_bytes()).hexdigest(),
                'duration': duration, 'music_gain_db': config.get('music_gain_db', -6), 'sample_rate': SR,
                'music_decoded_duration': source_duration, 'music_alignment_samples': alignment_samples,
                'peak_dbfs': 20*np.log10(max(1e-12, float(np.max(np.abs(audio))))),
                'master_gain': attenuation, 'engine_bed': bed, 'events': config.get('sfx', [])}
    if narration_report:
        metadata['narration'] = {'script': config['narration'], 'voice': narration_report['voice'],
                                 'cue_count': len(narration_report['cues']),
                                 'speech_lufs_before_master': narration_report['speech_lufs'],
                                 'music_mode': narration_report['music_mode'],
                                 'music_duck_db': narration_report['duck_db'],
                                 'music_envelope_min': float(music_envelope.min()),
                                 'music_envelope_max': float(music_envelope.max())}
    write_json(out / 'soundtrack.json', metadata)
    print(json.dumps({'soundtrack': project_reference(target), **metadata}, ensure_ascii=False, indent=2))
    return target


def analyze(path, output):
    audio = decode(path, channels=1)[:, 0]
    step = round(.01*SR)
    count = len(audio)//step
    rms = np.sqrt(np.mean(audio[:count*step].reshape(count, step)**2, axis=1))
    output.mkdir(parents=True, exist_ok=True)
    np.savetxt(output / 'rms-10ms.csv', np.column_stack((np.arange(count)*step/SR,
               20*np.log10(np.maximum(rms, 1e-10)))), delimiter=',', header='seconds,rms_dbfs', comments='')
    data = {'file': project_reference(path), 'paths_relative_to': 'project_root',
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'decoded_duration': len(audio)/SR, 'sample_rate': SR,
            'frames_30fps': int(np.ceil(len(audio)/SR*30)),
            'note': '10ms RMS 仅用于查找候选落点；实际高潮须结合编曲和试听确认，不能自动视为重拍'}
    write_json(output / 'music-analysis.json', data)
    print(json.dumps(data, ensure_ascii=False, indent=2))
