"""Standalone local animatics and media checks; editorial judgement stays with the creator."""

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import wave

from PIL import Image, ImageDraw, ImageFont

from . import render
from .finalize import probe
from .mix import mix
from .narration import cue_signature, settings as narration_settings
from .project import ROOT, load, music_path, read_json, write_json

SHOT_FIELDS = ('scene', 'subject', 'action', 'cause', 'result', 'new_information',
               'composition', 'transition')
ID = re.compile(r'^[A-Za-z0-9_-]{1,64}$')


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate_shots(data, plan, narration_ids=None):
    """Validate event descriptions and complete timing; aesthetic repetition remains a warning."""
    shots = data.get('shots') if isinstance(data, dict) else data
    errors, warnings = [], []
    if not isinstance(shots, list) or not shots:
        return {'ok': False, 'errors': ['shots.json must contain a nonempty shots array'], 'warnings': []}
    previous_end, previous, ids = 0.0, None, set()
    for index, shot in enumerate(shots):
        label = f'shot[{index}]'
        if not isinstance(shot, dict):
            errors.append(f'{label} must be an object')
            continue
        sid = shot.get('id')
        if not isinstance(sid, str) or not ID.fullmatch(sid) or sid in ids:
            errors.append(f'{label} needs a unique safe id')
        else:
            ids.add(sid)
            label = sid
        start, end = shot.get('start'), shot.get('end')
        if not finite(start) or not finite(end) or not 0 <= start < end <= plan['duration'] + .001:
            errors.append(f'{label} has invalid start/end')
        else:
            if abs(start - previous_end) > .001:
                errors.append(f'{label} starts at {start}; expected continuous time {previous_end}')
            previous_end = end
        for field in SHOT_FIELDS:
            if not isinstance(shot.get(field), str) or not shot[field].strip():
                errors.append(f'{label} needs nonempty {field}')
        if not isinstance(shot.get('repetition_reason'), str):
            errors.append(f'{label} needs repetition_reason (empty is allowed for a new view)')
        cue_ids = shot.get('narration_ids')
        if not isinstance(cue_ids, list) or any(not isinstance(value, str) for value in cue_ids):
            errors.append(f'{label} needs a narration_ids array (empty is allowed for music-only shots)')
        elif narration_ids is not None:
            unknown = sorted(set(cue_ids) - set(narration_ids))
            if unknown:
                errors.append(f'{label} references unknown narration ids: {unknown}')
        if previous and any(shot.get(field) == previous.get(field) for field in ('subject', 'composition')):
            warnings.append({'shot_id': sid, 'type': 'similar_adjacent_view',
                             'reason': shot.get('repetition_reason', ''),
                             'message': 'Review the actual sequence and its narrative reason; repetition alone is not a failure.'})
        previous = shot
    if abs(previous_end - plan['duration']) > .001:
        errors.append(f'Shots end at {previous_end}; full music duration is {plan["duration"]}')
    return {'ok': not errors, 'shot_count': len(shots), 'duration': plan['duration'],
            'errors': errors, 'warnings': warnings,
            'limitations': 'Text completeness and timing do not prove visible events or visual quality.'}


def read_shots(folder, config, plan):
    data = read_json(folder / 'shots.json')
    narration_ids = None
    if config.get('narration'):
        narration_ids = [cue['id'] for cue in read_json(folder / config['narration']).get('cues', [])]
    report = validate_shots(data, plan, narration_ids)
    shots = data['shots'] if isinstance(data, dict) else data
    return shots, report


def audio_input_signature(folder, config, plan):
    inputs = {'duration': plan['duration'], 'music_sha256': sha256(music_path(folder, config)),
              'music_gain_db': config.get('music_gain_db', -6),
              'ambience_gain': config.get('ambience_gain', .0008),
              'engine_bed': config.get('engine_bed'), 'sfx': config.get('sfx', []),
              'mix_code': sha256(Path(__file__).with_name('mix.py')),
              'narration_code': sha256(Path(__file__).with_name('narration.py'))}
    if config.get('narration'):
        inputs['narration_script_sha256'] = sha256(folder / config['narration'])
        inputs['voice_caches'] = {cue['id']: sha256(folder / 'audio/narration' / cue['id'] / 'source.wav')
                                  for cue in narration_settings(folder, config, plan)['cues']}
    return hashlib.sha256(json.dumps(inputs, sort_keys=True).encode('utf-8')).hexdigest()


def mix_with_receipt(folder, config, plan):
    """Bind the existing deterministic mix to its actual current inputs and output bytes."""
    signature = audio_input_signature(folder, config, plan)
    soundtrack = mix(folder, config, plan)
    if signature != audio_input_signature(folder, config, plan):
        raise ValueError('Audio inputs changed during mixing; rerun the current version')
    out = folder / config.get('output', 'build')
    receipt = {'input_sha256': signature, 'soundtrack_sha256': sha256(soundtrack),
               'mix_report_sha256': sha256(out / 'soundtrack.json')}
    if config.get('narration'):
        receipt['timing_report_sha256'] = sha256(out / 'narration-timing.json')
    write_json(out / 'audio-inputs.json', receipt)
    return soundtrack


def audio_audit(folder, config, plan):
    """Check actual cached voice and measured placements; never claim subjective listening."""
    out = folder / config.get('output', 'build')
    errors, warnings, gaps = [], [], []
    soundtrack = out / 'soundtrack.wav'
    result = {'ok': False, 'errors': errors, 'warnings': warnings, 'paragraph_gaps': gaps,
              'subjective_listening': 'not_performed',
              'limitations': 'Timing and gain checks cannot assess pronunciation, naturalness, or emotional delivery.'}
    try:
        with wave.open(str(soundtrack), 'rb') as stream:
            actual_duration = stream.getnframes() / stream.getframerate()
        result['soundtrack_duration'] = actual_duration
        result['soundtrack_sha256'] = sha256(soundtrack)
        receipt = read_json(out / 'audio-inputs.json')
        if (receipt.get('input_sha256') != audio_input_signature(folder, config, plan)
                or receipt.get('soundtrack_sha256') != result['soundtrack_sha256']
                or receipt.get('mix_report_sha256') != sha256(out / 'soundtrack.json')):
            errors.append('Audio input/output receipt is stale; run python -m tools.video_review mix again')
        result['audio_input_sha256'] = receipt.get('input_sha256')
        if abs(actual_duration - plan['duration']) > .025:
            errors.append('Soundtrack duration differs from full plan duration')
        mix_report = read_json(out / 'soundtrack.json')
        if mix_report.get('music_sha256') != sha256(music_path(folder, config)):
            errors.append('Soundtrack metadata references a different music file')
        if mix_report.get('music_gain_db') != config.get('music_gain_db', -6):
            errors.append('Music gain differs from the current configuration')
        if mix_report.get('events') != config.get('sfx', []):
            errors.append('Sound effects differ from the current configuration')
        result['narration_enabled'] = bool(config.get('narration'))
        if config.get('narration'):
            data = narration_settings(folder, config, plan)
            timing_path = out / 'narration-timing.json'
            timing = read_json(timing_path)
            result['narration_timing_sha256'] = sha256(timing_path)
            if receipt.get('timing_report_sha256') != result['narration_timing_sha256']:
                errors.append('Narration timing changed after mixing; run python -m tools.video_review mix again')
            result['narration_script_sha256'] = sha256(folder / config['narration'])
            measured = timing.get('cues', [])
            if len(measured) != len(data['cues']):
                errors.append('Narration timing has a different number of paragraphs')
            if data.get('music_mode', 'constant') != 'constant' or timing.get('music_mode') != 'constant':
                errors.append('Project default requires constant music gain, without sentence ducking')
            bed = mix_report.get('narration', {})
            if bed.get('music_mode') != 'constant' or bed.get('music_envelope_min') != 1 or bed.get('music_envelope_max') != 1:
                errors.append('Actual mix report does not confirm a constant music envelope')
            previous_end = None
            result['cues'] = []
            for cue, actual in zip(data['cues'], measured):
                sid = cue['id']
                if any(cue.get(key) != actual.get(key) for key in ('id', 'text', 'start', 'end')):
                    errors.append(f'{sid}: timing report is stale')
                end = actual.get('actual_end')
                if not finite(end) or not cue['start'] < end <= cue['end'] + .025:
                    errors.append(f'{sid}: measured voice exceeds or falls outside its time window')
                    continue
                if actual.get('tempo', 1) > 1.0001:
                    errors.append(f'{sid}: voice was time-stretched; rewrite/replan instead')
                cache = folder / 'audio/narration' / sid
                metadata = read_json(cache / 'source.json')
                current_hash = sha256(cache / 'source.wav')
                if metadata.get('signature') != cue_signature(data, cue) or metadata.get('sha256') != current_hash or actual.get('sha256') != current_hash:
                    errors.append(f'{sid}: current text/audio does not match the measured voice cache')
                for start, stop in data.get('protected_gaps', []):
                    if cue['start'] < stop and end > start:
                        errors.append(f'{sid}: measured voice enters protected music interval')
                if previous_end is not None:
                    gap = cue['start'] - previous_end
                    protected = any(a < cue['start'] and b > previous_end for a, b in data.get('protected_gaps', []))
                    record = {'before': sid, 'start': previous_end, 'end': cue['start'],
                              'seconds': round(gap, 4), 'overlaps_protected_music': protected}
                    gaps.append(record)
                    if gap < -.025:
                        errors.append(f'{sid}: actual voice overlaps previous paragraph')
                    elif gap > 1 and not protected:
                        warnings.append({'type': 'long_paragraph_gap', **record,
                                         'message': 'Check whether this pause serves observation or meaning; do not automatically remove it.'})
                previous_end = end
                result['cues'].append({'id': sid, 'start': cue['start'], 'actual_end': end,
                                       'allocated_end': cue['end'], 'tempo': actual.get('tempo', 1)})
    except (OSError, ValueError, KeyError, TypeError, wave.Error) as error:
        errors.append(str(error))
    result['ok'] = not errors
    return result


def shot_times(shot, plan):
    start, end, fps = shot['start'], shot['end'], plan['fps']
    last = (plan['frames'] - 1) / fps
    return [min(last, round(value * fps) / fps) for value in (start, (start + end) / 2, max(start, end - 1 / fps))]


def sample_times(shots, plan):
    fps, duration = plan['fps'], plan['duration']
    last = (plan['frames'] - 1) / fps
    impact = plan['impact_frame'] / fps
    values = [0, 1.2, 2.4, impact - .733333333, impact - .233333333,
              impact - 1 / fps, impact, impact + 1 / fps, impact + .066666667,
              impact + .466666667, impact + .966666667, last]
    for shot in shots:
        values.extend(shot_times(shot, plan))
    return sorted({min(last, round(value * fps) / fps) for value in values if 0 <= value < duration})


@contextmanager
def configured_renderer(folder, config, plan, destination):
    names = ('ROOT', 'OUT', 'HTTP_ROOT', 'ENTRY', 'FPS', 'FRAMES', 'TIMES', 'SOURCE_NAMES', 'MOTION_RANGES')
    previous = {name: getattr(render, name) for name in names}
    try:
        render.configure(ROOT, folder, config, plan)
        render.OUT = destination
        destination.mkdir(parents=True, exist_ok=True)
        yield
    finally:
        for name, value in previous.items():
            setattr(render, name, value)


def make_shot_sheets(folder, shots, plan, destination, image_paths=None, prefix='shots'):
    images, moments = [], []
    font = ImageFont.truetype(str(ROOT / 'assets/fonts/Lora.ttf'), 36)
    for shot in shots:
        seconds = shot_times(shot, plan)[1]
        source = image_paths[seconds] if image_paths is not None else destination / f'{seconds:010.6f}.png'
        image = Image.open(source).convert('RGB')
        draw = ImageDraw.Draw(image)
        draw.text((24, 24), shot['id'], font=font, fill='white', stroke_width=3, stroke_fill='black')
        images.append(image)
        moments.append(seconds)
    sheets = []
    for offset in range(0, len(images), 9):
        target = destination / f'{prefix}_{offset // 9 + 1}.jpg'
        render.make_sheet(images[offset:offset + 9], moments[offset:offset + 9], target, 3)
        sheets.append(target.relative_to(folder).as_posix())
    return sheets


def evidence(slug, destination=None):
    folder, config, plan = load(slug)
    destination = destination or folder / config.get('output', 'build') / 'animatic'
    shots, shot_report = read_shots(folder, config, plan)
    destination.mkdir(parents=True, exist_ok=True)
    write_json(destination / 'shot-audit.json', shot_report)
    if not shot_report['ok']:
        raise ValueError('Shot audit failed: ' + '; '.join(shot_report['errors']))
    audio = audio_audit(folder, config, plan)
    write_json(destination / 'audio-audit.json', audio)
    if not audio['ok']:
        raise ValueError('Audio audit failed: ' + '; '.join(audio['errors']))
    shots_hash = sha256(folder / 'shots.json')
    with configured_renderer(folder, config, plan, destination):
        signature = render.source_signature()
        render.preview(sample_times(shots, plan))
        if signature != render.source_signature() or shots_hash != sha256(folder / 'shots.json'):
            raise ValueError('Source changed during evidence generation; rerun for the current version')
        layout = read_json(destination / 'review/layout_audit.json')
    if (audio_input_signature(folder, config, plan) != audio['audio_input_sha256']
            or sha256(folder / config.get('output', 'build') / 'soundtrack.wav') != audio['soundtrack_sha256']):
        raise ValueError('Audio changed during evidence generation; rerun the current version')
    sheets = make_shot_sheets(folder, shots, plan, destination / 'review')
    relative = lambda path: path.relative_to(folder).as_posix()
    manifest = {'schema_version': 1, 'kind': 'creative_evidence', 'slug': slug,
                'created_at': datetime.now(timezone.utc).isoformat(), 'paths_relative_to': 'episode',
                'source_sha256': signature, 'shots_sha256': shots_hash,
                'audio_sha256': audio['soundtrack_sha256'], 'plan_sha256': sha256(folder / config.get('plan', 'plan.json')),
                'duration': plan['duration'], 'fps': plan['fps'], 'frames': plan['frames'],
                'soundtrack': relative(folder / config.get('output', 'build') / 'soundtrack.wav'),
                'images': [{'time': item['time'], 'file': relative(destination / 'review' / item['file'])} for item in layout['frames']],
                'shots': [{'id': shot['id'], 'start': shot['start'], 'end': shot['end'],
                           'action_frames': [{'phase': phase, 'time': seconds,
                                              'file': relative(destination / 'review' / f'{seconds:010.6f}.png')}
                                             for phase, seconds in zip(('begin', 'middle', 'end'), shot_times(shot, plan))]}
                          for shot in shots],
                'contact_sheets': sheets,
                'overview_sheets': [relative(destination / 'review' / f'overview_{index + 1}.jpg')
                                    for index in range(math.ceil(len(layout['frames']) / 12))],
                'motion_strips': [{'file': relative(destination / 'review' / item['file']), 'times': item['times']} for item in layout['transition_strips']],
                'layout_issue_frames': layout['layout_issue_frames'],
                'technical_audio_ok': audio['ok'], 'shot_timing_ok': shot_report['ok'],
                'creative_approval': 'not_assessed', 'subjective_listening': 'not_performed',
                'continuous_visual_review': 'not_performed',
                'limitations': 'Evidence files exist; a reviewer must actually inspect them. Image sampling is not continuous viewing or listening.'}
    write_json(destination / 'manifest.json', manifest)
    if layout['layout_issue_frames']:
        raise ValueError(f'Layout audit found {layout["layout_issue_frames"]} failing frames; inspect saved evidence')
    return manifest


def sample_range(plan, start, end):
    """Return a half-open frame range on the original timeline, covering the requested seconds."""
    if not finite(start) or not finite(end) or not 0 <= start < end <= plan['duration']:
        raise ValueError('Sample requires 0 <= start < end <= plan.duration')
    fps = plan['fps']
    return math.floor(start * fps + 1e-8), min(plan['frames'], math.ceil(end * fps - 1e-8))


def build_sample(slug, start, end, jobs=2, resume=False):
    """Render a mixed short excerpt without requiring completed shots or changing production state."""
    folder, config, plan = load(slug)
    first, stop = sample_range(plan, start, end)
    if jobs < 1:
        raise ValueError('jobs must be positive')
    original_config = (folder / 'film.json').read_bytes()
    fps = plan['fps']
    seconds = (stop - first) / fps
    destination = folder / config.get('output', 'build') / 'samples' / f'{first:06d}-{stop:06d}'
    destination.mkdir(parents=True, exist_ok=True)
    (destination / 'manifest.json').unlink(missing_ok=True)
    soundtrack = mix_with_receipt(folder, config, plan)
    audio_report = audio_audit(folder, config, plan)
    write_json(destination / 'audio-audit.json', audio_report)
    if not audio_report['ok']:
        raise ValueError('Sample audio audit failed: ' + '; '.join(audio_report['errors']))
    audio_hash = sha256(soundtrack)
    audio_inputs = audio_input_signature(folder, config, plan)
    frames = {first, (first + stop - 1) // 2, stop - 1}
    impact = plan.get('impact_frame', -2)
    frames.update(frame for frame in (impact - 1, impact, impact + 1) if first <= frame < stop)
    # A local action check must not render unrelated full-film motion strips.
    with configured_renderer(folder, config, plan, destination):
        render.MOTION_RANGES = []
        signature = render.source_signature()
        render.preview([frame / fps for frame in sorted(frames)])
        layout = read_json(destination / 'review/layout_audit.json')
        if layout['layout_issue_frames']:
            raise ValueError('Sample layout audit failed; inspect saved review frames')
        render.render(first, stop, jobs, 'sample-picture', resume=resume)
        if signature != render.source_signature():
            raise ValueError('Source changed during sample rendering; rerun the current version')
    target = destination / 'sample.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(destination / 'sample-picture.mp4'),
                    '-ss', f'{first / fps:.9f}', '-i', str(soundtrack),
                    '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy',
                    '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-t', f'{seconds:.9f}',
                    '-movflags', '+faststart', str(target)], check=True)
    info = probe(target)
    video = next(stream for stream in info['streams'] if stream['codec_type'] == 'video')
    audio = next(stream for stream in info['streams'] if stream['codec_type'] == 'audio')
    expected_audio = min(stop / fps, plan['duration']) - first / fps
    with configured_renderer(folder, config, plan, destination):
        current = render.source_signature()
    if (current != signature or sha256(soundtrack) != audio_hash
            or audio_input_signature(folder, config, plan) != audio_inputs):
        raise ValueError('Source or audio changed during sample export; rerun the current version')
    checks = {'dimensions': (video['width'], video['height']) == (1920, 1080),
              'fps': video['r_frame_rate'] == '30/1',
              'frames': int(video.get('nb_frames', 0)) == stop - first,
              'video_duration': abs(float(video['duration']) - seconds) < .001,
              'audio_duration': abs(float(audio['duration']) - expected_audio) < .025,
              'production_flag_unchanged': original_config == (folder / 'film.json').read_bytes()}
    relative = lambda path: path.relative_to(folder).as_posix()
    manifest = {'schema_version': 1, 'kind': 'action_sample', 'slug': slug,
                'created_at': datetime.now(timezone.utc).isoformat(), 'paths_relative_to': 'episode',
                'requested_start': start, 'requested_end': end,
                'start_frame': first, 'end_frame_exclusive': stop,
                'source_start': first / fps, 'source_end': stop / fps,
                'frames': stop - first, 'fps': fps, 'duration': seconds,
                'sample': relative(target), 'sample_sha256': sha256(target),
                'source_sha256': signature, 'audio_sha256': audio_hash,
                'audio_input_sha256': audio_inputs,
                'images': [{'source_frame': round(item['time'] * fps), 'source_time': item['time'],
                            'file': relative(destination / 'review' / item['file'])} for item in layout['frames']],
                'media_checks': checks, 'all_media_checks_pass': all(checks.values()),
                'creative_approval': 'not_assessed', 'continuous_visual_review': 'not_performed',
                'subjective_listening': 'not_performed'}
    write_json(destination / 'manifest.json', manifest)
    if not all(checks.values()):
        raise ValueError('Sample media checks failed; see manifest.json')
    return manifest


def build_animatic(slug, jobs=2, resume=False):
    folder, config, plan = load(slug)
    original_config = (folder / 'film.json').read_bytes()
    destination = folder / config.get('output', 'build') / 'animatic'
    shots, shot_report = read_shots(folder, config, plan)
    if not shot_report['ok']:
        raise ValueError('Shot audit failed: ' + '; '.join(shot_report['errors']))
    soundtrack = mix_with_receipt(folder, config, plan)
    manifest = evidence(slug, destination)
    with configured_renderer(folder, config, plan, destination):
        render.render(0, plan['frames'], jobs, 'animatic-picture', resume=resume)
        if render.source_signature() != manifest['source_sha256'] or sha256(soundtrack) != manifest['audio_sha256'] or sha256(folder / 'shots.json') != manifest['shots_sha256']:
            raise ValueError('Source or audio changed during animatic rendering; rerun the current version')
    target = destination / 'animatic.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(destination / 'animatic-picture.mp4'),
                    '-i', str(soundtrack), '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy',
                    '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-t', f'{plan["frames"] / plan["fps"]:.9f}',
                    '-movflags', '+faststart', str(target)], check=True)
    info = probe(target)
    video = next(stream for stream in info['streams'] if stream['codec_type'] == 'video')
    audio = next(stream for stream in info['streams'] if stream['codec_type'] == 'audio')
    checks = {'dimensions': (video['width'], video['height']) == (1920, 1080),
              'fps': video['r_frame_rate'] == '30/1', 'frames': int(video.get('nb_frames', 0)) == plan['frames'],
              'full_audio_duration': abs(float(audio['duration']) - plan['duration']) < .025,
              'full_video_duration': abs(float(video['duration']) - plan['frames'] / plan['fps']) < .001,
              'production_flag_unchanged': original_config == (folder / 'film.json').read_bytes()}
    manifest.update({'animatic': target.relative_to(folder).as_posix(), 'animatic_sha256': sha256(target),
                     'media_checks': checks, 'all_media_checks_pass': all(checks.values())})
    write_json(destination / 'manifest.json', manifest)
    if not all(checks.values()):
        raise ValueError('Animatic media checks failed; see manifest.json')
    return manifest


def final_evidence(folder, config, plan, shots):
    """Sample the encoded final video, paginating every shot's actual decoded frames."""
    out = folder / config.get('output', 'build')
    destination = out / 'review/final-evidence'
    destination.mkdir(parents=True, exist_ok=True)
    target, soundtrack = out / 'final_video.mp4', out / 'soundtrack.wav'
    validation_path = out / 'review/validation.json'
    validation = read_json(validation_path)
    video_hash = sha256(target)
    if not validation.get('all_technical_checks_pass') or validation.get('sha256') != video_hash:
        raise ValueError('Final evidence requires current successful encoded-video validation')
    shots_hash, plan_hash = sha256(folder / 'shots.json'), sha256(folder / config.get('plan', 'plan.json'))
    audio_hash, validation_hash = sha256(soundtrack), sha256(validation_path)
    with configured_renderer(folder, config, plan, out):
        signature = render.source_signature()
    if (read_json(out / 'picture.render.json').get('source_sha256') != signature
            or read_json(out / 'review/layout_audit.json').get('source_sha256') != signature):
        raise ValueError('Sources changed after final encoding; cannot label old frames as current evidence')
    frames = sorted({round(seconds * plan['fps']) for seconds in sample_times(shots, plan)})
    image_paths = {frame / plan['fps']: destination / f'encoded_{index + 1:04d}.png'
                   for index, frame in enumerate(frames)}
    # Remove only this export's known files so incomplete extraction cannot reuse an old PNG.
    (destination / 'manifest.json').unlink(missing_ok=True)
    for path in image_paths.values():
        path.unlink(missing_ok=True)
    expression = '+'.join(f'eq(n\\,{frame})' for frame in frames)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(target), '-map', '0:v:0',
                    '-vf', 'select=' + expression, '-fps_mode', 'vfr', '-start_number', '1',
                    str(destination / 'encoded_%04d.png')], check=True)
    images = []
    for path in image_paths.values():
        image = Image.open(path).convert('RGB')
        if image.size != (1920, 1080):
            raise ValueError('Encoded evidence frame has unexpected dimensions: ' + path.name)
        images.append(image)
    times = list(image_paths)
    relative = lambda path: path.relative_to(folder).as_posix()
    overview = []
    for offset in range(0, len(images), 12):
        path = destination / f'encoded_overview_{offset // 12 + 1}.jpg'
        render.make_sheet(images[offset:offset + 12], times[offset:offset + 12], path, 3)
        overview.append(relative(path))
    contact = make_shot_sheets(folder, shots, plan, destination, image_paths, 'encoded_shots')
    with configured_renderer(folder, config, plan, out):
        if (render.source_signature() != signature or sha256(target) != video_hash
                or sha256(folder / 'shots.json') != shots_hash
                or sha256(folder / config.get('plan', 'plan.json')) != plan_hash
                or sha256(soundtrack) != audio_hash or sha256(validation_path) != validation_hash):
            raise ValueError('Sources or final media changed during encoded evidence extraction')
    manifest = {'schema_version': 1, 'kind': 'final_creative_evidence', 'slug': folder.name,
                'created_at': datetime.now(timezone.utc).isoformat(), 'paths_relative_to': 'episode',
                'source_sha256': signature, 'shots_sha256': shots_hash, 'plan_sha256': plan_hash,
                'audio_sha256': audio_hash, 'validation_sha256': validation_hash,
                'final_video': relative(target), 'final_video_sha256': video_hash,
                'soundtrack': relative(soundtrack), 'duration': plan['duration'],
                'fps': plan['fps'], 'frames': plan['frames'],
                'images': [{'frame': frame, 'time': frame / plan['fps'],
                            'file': relative(image_paths[frame / plan['fps']]),
                            'sha256': sha256(image_paths[frame / plan['fps']])} for frame in frames],
                'shots': [{'id': shot['id'], 'start': shot['start'], 'end': shot['end'],
                           'action_frames': [{'phase': phase, 'time': seconds, 'frame': round(seconds * plan['fps']),
                                              'file': relative(image_paths[seconds])}
                                             for phase, seconds in zip(('begin', 'middle', 'end'), shot_times(shot, plan))]}
                          for shot in shots],
                'overview_sheets': overview, 'contact_sheets': contact,
                'all_technical_checks_pass': validation['all_technical_checks_pass'],
                'creative_approval': 'not_assessed', 'subjective_listening': 'not_performed',
                'continuous_visual_review': 'not_performed',
                'limitations': 'Frames are decoded from the final MP4 across the full timeline. Sampling does not prove continuous viewing or subjective listening.'}
    write_json(destination / 'manifest.json', manifest)
    return manifest


def finalize(slug, jobs=2):
    folder, config, plan = load(slug)
    if not config.get('production_ready'):
        raise ValueError('Creative review must approve the current version before final production')
    shots, report = read_shots(folder, config, plan)
    if not report['ok']:
        raise ValueError('Shot timing is invalid: ' + '; '.join(report['errors']))
    mix_with_receipt(folder, config, plan)
    audio = audio_audit(folder, config, plan)
    review = folder / config.get('output', 'build') / 'review'
    review.mkdir(parents=True, exist_ok=True)
    write_json(review / 'audio-audit.json', audio)
    if not audio['ok']:
        raise ValueError('Final audio audit failed: ' + '; '.join(audio['errors']))
    for arguments in [('preview', slug), ('render', slug, '--jobs', str(jobs)), ('finalize', slug)]:
        subprocess.run([sys.executable, str(ROOT / 'vibe.py'), *arguments], cwd=ROOT, check=True)
    final_evidence(folder, config, plan, shots)
    return read_json(folder / config.get('output', 'build') / 'review/validation.json')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['validate', 'mix', 'audio', 'evidence', 'sample', 'animatic', 'final-evidence', 'finalize'])
    parser.add_argument('slug')
    parser.add_argument('--jobs', type=int, default=2)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--start', type=float, help='Sample start in original-film seconds')
    parser.add_argument('--end', type=float, help='Sample end in original-film seconds')
    args = parser.parse_args()
    try:
        if args.command == 'validate':
            folder, config, plan = load(args.slug)
            _, result = read_shots(folder, config, plan)
        elif args.command == 'mix':
            folder, config, plan = load(args.slug)
            mix_with_receipt(folder, config, plan)
            result = audio_audit(folder, config, plan)
        elif args.command == 'audio':
            result = audio_audit(*load(args.slug))
        elif args.command == 'evidence':
            result = evidence(args.slug)
        elif args.command == 'sample':
            result = build_sample(args.slug, args.start, args.end, args.jobs, args.resume)
        elif args.command == 'animatic':
            result = build_animatic(args.slug, args.jobs, args.resume)
        elif args.command == 'final-evidence':
            folder, config, plan = load(args.slug)
            shots, report = read_shots(folder, config, plan)
            if not report['ok']:
                raise ValueError('Shot timing is invalid: ' + '; '.join(report['errors']))
            result = final_evidence(folder, config, plan, shots)
        else:
            result = finalize(args.slug, args.jobs)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if result.get('ok') is False else 0
    except (ValueError, OSError, KeyError, subprocess.SubprocessError) as error:
        print(json.dumps({'ok': False, 'error': str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
