import hashlib
import json
import re
import subprocess

import numpy as np
from PIL import Image

from .project import read_json, write_json
from .render import make_sheet


def run(arguments, **kwargs):
    return subprocess.run(arguments, check=True, **kwargs)


def probe(path):
    return json.loads(run(['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of',
                          'json', str(path)], capture_output=True, encoding='utf-8').stdout)


def pcm(path, start, duration):
    raw = run(['ffmpeg', '-v', 'error', '-ss', str(start), '-i', str(path), '-t', str(duration),
               '-map', '0:a:0', '-ac', '1', '-ar', '22050', '-f', 'f32le', '-'], capture_output=True).stdout
    return np.frombuffer(raw, dtype='<f4')


def sync(final, soundtrack, plan):
    impact = plan['impact_frame']/plan['fps']
    start = max(0, min(impact-4, plan['duration']-2))
    duration = min(8, plan['duration']-start)
    left, right = pcm(final, start, duration), pcm(soundtrack, start, duration)
    count = min(len(left), len(right))
    if count < 22050:
        raise ValueError('至少需要一秒音频才能进行同步检测')
    left, right = left[:count], right[:count]
    size = 1 << int(np.ceil(np.log2(count*2)))
    correlation = np.fft.irfft(np.fft.rfft(left, size)*np.conj(np.fft.rfft(right, size)), size)
    limit = min(round(.25*22050), count-1)
    lags = np.arange(-limit, limit+1)
    lag = int(lags[np.argmax(correlation[lags % size])])
    return {'segment_start': start, 'segment_duration': duration, 'lag_seconds': lag/22050,
            'correlation_zero_lag': float(np.corrcoef(left, right)[0, 1]),
            'limitation': '验证封装后的音轨时序；不代替音乐与动作的主观听感判断'}


def finalize(folder, config, plan, signature):
    out = folder / config.get('output', 'build')
    review = out / 'review'
    review.mkdir(parents=True, exist_ok=True)
    picture, soundtrack = out / 'picture.mp4', out / 'soundtrack.wav'
    metadata = read_json(out / 'picture.render.json')
    layout = read_json(review / 'layout_audit.json')
    if metadata.get('start') != 0 or metadata.get('frames') != plan['frames']:
        raise ValueError('picture.mp4 不是从 0 开始的完整渲染')
    if not metadata.get('source_sha256') == signature == layout.get('source_sha256'):
        raise ValueError('源文件已变化，重新预览和渲染后再合成')
    if layout.get('layout_issue_frames') != 0:
        raise ValueError('预览仍有文字几何越界问题')
    if not config.get('production_ready'):
        raise ValueError('仍是制作骨架，完成内容与场景后才能交付成片')
    target = out / 'final_video.mp4'
    run(['ffmpeg', '-v', 'error', '-y', '-i', str(picture), '-i', str(soundtrack), '-map',
         '0:v:0', '-map', '1:a:0', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '256k', '-ar',
         '48000', '-t', f'{plan["frames"]/plan["fps"]:.9f}', '-movflags', '+faststart', str(target)])
    info = probe(target)
    video = next(x for x in info['streams'] if x['codec_type'] == 'video')
    audio = next(x for x in info['streams'] if x['codec_type'] == 'audio')
    checks = {
        'dimensions': video['width'] == 1920 and video['height'] == 1080,
        'fps': video['r_frame_rate'] == '30/1' and video['avg_frame_rate'] == '30/1',
        'frames': int(video.get('nb_frames', 0)) == plan['frames'],
        'codecs': video['codec_name'] == 'h264' and audio['codec_name'] == 'aac',
        'audio_duration': abs(float(audio['duration'])-plan['duration']) < .025,
        'audio_video_gap': abs(float(video['duration'])-float(audio['duration'])) < .04,
        'preview_matches_source': layout['source_sha256'] == signature,
        'render_matches_source': metadata['source_sha256'] == signature,
        'source_text_bounds': layout['layout_issue_frames'] == 0,
    }
    decoded = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-xerror', '-i', str(target),
                              '-map', '0:v:0', '-map', '0:a:0', '-vf',
                              'blackdetect=d=0.5:pix_th=0.005:pic_th=0.995', '-af',
                              'loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json', '-f', 'null', '-'],
                             capture_output=True, encoding='utf-8')
    (review / 'decode_and_audio.log').write_text(decoded.stderr, encoding='utf-8')
    checks['full_decode'] = decoded.returncode == 0
    start, end = decoded.stderr.rfind('{'), decoded.stderr.rfind('}')
    loudness = json.loads(decoded.stderr[start:end+1]) if start >= 0 and end > start else None
    checks['true_peak'] = loudness is not None and float(loudness['input_tp']) <= -1.5
    synchronization = sync(target, soundtrack, plan)
    checks['mux_audio_sync'] = abs(synchronization['lag_seconds']) < 1/30 and synchronization['correlation_zero_lag'] > .95
    frames = sorted(set(round(t*30) for t in config.get('review_times', config['preview_times'])))
    expression = '+'.join(f'eq(n\\,{n})' for n in frames)
    run(['ffmpeg', '-v', 'error', '-y', '-i', str(target), '-vf', 'select='+expression,
         '-fps_mode', 'vfr', str(review / 'encoded_%03d.png')])
    entries = [{'frame': frame, 'seconds': frame/30, 'file': f'encoded_{i+1:03d}.png'} for i, frame in enumerate(frames)]
    make_sheet([Image.open(review/x['file']).convert('RGB') for x in entries],
               [x['seconds'] for x in entries], review / 'encoded_review.jpg', 4)
    black = [{'start': float(a), 'end': float(b), 'duration': float(c)} for a,b,c in re.findall(
        r'black_start:([\d.]+)\s+black_end:([\d.]+)\s+black_duration:([\d.]+)', decoded.stderr)]
    result = {'output': str(target), 'checks': checks, 'all_technical_checks_pass': all(checks.values()),
              'video_duration': float(video['duration']), 'audio_duration': float(audio['duration']),
              'loudness': loudness, 'audio_mux_sync': synchronization, 'encoded_frames': entries,
              'near_total_black_intervals': black,
              'black_interval_note': '报告供人工判断；有意设计的暗场不自动判错',
              'manual_visual_review': '待查看 encoded_review.jpg 并写入 review/人工复核.md',
              'subjective_listening': '程序不执行主观试听',
              'sha256': hashlib.sha256(target.read_bytes()).hexdigest(), 'size_bytes': target.stat().st_size}
    write_json(review / 'final_probe.json', info)
    write_json(review / 'validation.json', result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not all(checks.values()):
        raise RuntimeError('检查失败: '+', '.join(k for k,v in checks.items() if not v))
    return target
