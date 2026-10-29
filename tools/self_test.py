"""A fresh online voice and a synthetic ten-second film, isolated from creative episodes."""

from datetime import datetime, timezone
import hashlib
import json
import shutil
import uuid

import numpy as np

from . import render
from .doctor import diagnose
from .finalize import finalize
from .mix import SR
from .narration import save_wave, synthesize
from .project import ROOT, read_json, write_json
from .video_review import audio_audit, configured_renderer, mix_with_receipt


def self_test(jobs=2):
    if jobs < 1:
        raise ValueError('jobs must be positive')
    folder = ROOT / '.local' / ('self-test-' + datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-') + uuid.uuid4().hex[:6])
    folder.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT / 'templates/self-test', folder)
    manifest = {'kind': 'technical_self_test', 'created_at': datetime.now(timezone.utc).isoformat(),
                'ok': False, 'stage': 'local_dependencies', 'fresh_online_synthesis': False,
                'subjective_listening': 'not_performed', 'creative_approval': 'not_applicable',
                'folder': folder.relative_to(ROOT).as_posix()}
    try:
        print('SELF-TEST: checking local dependencies', flush=True)
        diagnostics = diagnose()
        write_json(folder / 'doctor.json', diagnostics)
        if not diagnostics['ok']:
            raise RuntimeError('Self-test dependencies failed; see doctor.json or run python bootstrap.py')
        plan = {'title': '工具链自检', 'anchor': '连接', 'fps': 30, 'duration': 10.0,
                'frames': 300, 'impact_frame': 150, 'subtitles': [
                    {'start': .5, 'end': 4.5, 'zh': '配音接通，动画开始。', 'en': 'Voice connected. Animation begins.'},
                    {'start': 5.2, 'end': 9.5, 'zh': '这是工具自检，不是创作样片。', 'en': 'A technical test, not a creative reference.'}]}
        config = {'entry': 'index.html', 'plan': 'plan.json', 'output': 'build',
                  'production_ready': True, 'test_only': True, 'music': 'test-music.wav',
                  'narration': 'narration.json', 'music_gain_db': -18, 'ambience_gain': 0,
                  'sources': ['index.html', 'scenes.js', 'plan.json', 'plan.js'],
                  'preview_times': [0, 1.5, 4.9, 5, 5.1, 9.99],
                  'review_times': [0, 1.5, 4.9, 5, 5.1, 9.99],
                  'sfx': [{'time': 5, 'kind': 'impact', 'volume': .12, 'duration': .45}]}
        narration = {'backend': 'edge', 'voice': 'zh-CN-YunjianNeural', 'rate': '+0%',
                     'target_lufs': -18, 'music_mode': 'constant', 'max_tempo': 1,
                     'protected_gaps': [[4.8, 5.2]],
                     'cues': [{'id': 'probe', 'start': .5, 'end': 4.5, 'text': '配音接通，动画开始。'}]}
        for name, value in [('film.json', config), ('plan.json', plan), ('narration.json', narration)]:
            write_json(folder / name, value)
        (folder / 'plan.js').write_text('window.FILM_PLAN=' + json.dumps(plan, ensure_ascii=False) + ';\n', encoding='utf-8')
        t = np.arange(10 * SR) / SR
        bed = (.055 * np.sin(2 * np.pi * 220 * t) + .035 * np.sin(2 * np.pi * 330 * t))
        bed *= np.minimum(t, 1) * np.minimum(10 - t, 1)
        save_wave(folder / 'test-music.wav', bed)
        manifest['stage'] = 'new_online_voice'
        print('SELF-TEST: requesting fresh Edge narration', flush=True)
        synthesize(folder, config, plan)
        voice = folder / 'audio/narration/probe/source.wav'
        manifest['fresh_online_synthesis'] = True
        manifest['voice_sha256'] = hashlib.sha256(voice.read_bytes()).hexdigest()
        manifest['stage'] = 'mix_and_render'
        mix_with_receipt(folder, config, plan)
        audio = audio_audit(folder, config, plan)
        write_json(folder / 'audio-audit.json', audio)
        if not audio['ok']:
            raise RuntimeError('Self-test audio audit failed: ' + '; '.join(audio['errors']))
        print('SELF-TEST: rendering 300 frames and verifying the encoded film', flush=True)
        with configured_renderer(folder, config, plan, folder / 'build'):
            render.preview()
            layout = read_json(folder / 'build/review/layout_audit.json')
            if layout['layout_issue_frames']:
                raise RuntimeError('Self-test layout check failed')
            render.render(0, plan['frames'], jobs, 'picture')
            manifest['stage'] = 'encoded_validation'
            target = finalize(folder, config, plan, render.source_signature())
        validation = read_json(folder / 'build/review/validation.json')
        manifest.update({'ok': validation['all_technical_checks_pass'], 'stage': 'complete',
                         'video': target.relative_to(ROOT).as_posix(), 'video_sha256': validation['sha256'],
                         'validation': (folder / 'build/review/validation.json').relative_to(ROOT).as_posix(),
                         'last_review_frame': max(entry['frame'] for entry in validation['encoded_frames'])})
    except Exception as error:
        manifest['error'] = str(error)
        raise
    finally:
        write_json(folder / 'self-test.json', manifest)
        write_json(ROOT / '.local/self-test-latest.json', manifest)
        print(json.dumps(manifest, ensure_ascii=False, indent=2), flush=True)
    return manifest
