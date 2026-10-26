import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def video_path(slug):
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', slug):
        raise ValueError('视频目录名使用小写英文、数字和连字符，例如 sunk-cost')
    return ROOT / 'videos' / slug


def load(slug):
    folder = video_path(slug)
    config = read_json(folder / 'film.json')
    plan = read_json(folder / config.get('plan', 'plan.json'))
    if plan.get('fps') != 30:
        raise ValueError('当前渲染工具支持 1920×1080、30fps')
    duration = float(plan['duration'])
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError('duration 必须为正有限数')
    if plan['frames'] != math.ceil(duration * 30 - 1e-8):
        raise ValueError('frames 应为 ceil(duration × 30)，不能截短音乐尾奏')
    impact = plan.get('impact_frame')
    if not isinstance(impact, int) or not 0 <= impact < plan['frames']:
        raise ValueError('impact_frame 必须是片内的零起算整数帧号')
    for field in ['entry', 'plan', 'output']:
        path = (folder / config.get(field, {'plan': 'plan.json', 'output': 'build'}.get(field, 'index.html'))).resolve()
        if not path.is_relative_to(folder.resolve()):
            raise ValueError(f'{field} 必须位于视频目录内')
    js = 'window.FILM_PLAN=' + json.dumps(plan, ensure_ascii=False) + ';\n'
    path = folder / 'plan.js'
    if not path.exists() or path.read_text(encoding='utf-8') != js:
        path.write_text(js, encoding='utf-8')
    for name in config['sources']:
        source = (folder / name).resolve()
        if not source.is_relative_to(folder.resolve()) or not source.is_file():
            raise ValueError(f'源文件不在视频目录内或不存在: {name}')
    previous_end = 0.0
    for cue in plan.get('subtitles', []):
        start, end = float(cue['start']), float(cue['end'])
        if not (0 <= start < end <= duration) or start < previous_end:
            raise ValueError(f'字幕时码无效或互相重叠: {cue}')
        if not cue.get('zh') or not cue.get('en'):
            raise ValueError('每条字幕须包含中文和英文')
        previous_end = end
    for t in config.get('preview_times', []) + config.get('review_times', []):
        if not 0 <= t < duration:
            raise ValueError(f'抽帧时间不在片内: {t}')
    for start, end, name in config.get('motion_ranges', []):
        if not 0 <= start < end < duration or not re.fullmatch(r'[a-z0-9_-]+', name):
            raise ValueError(f'动作检查区间无效: {name}')
    for event in config.get('sfx', []):
        if not (0 <= event['time'] < duration and event['duration'] > 0 and 0 <= event['volume'] <= 1):
            raise ValueError(f'音效参数无效: {event}')
    return folder, config, plan


def music_path(folder, config):
    path = (folder / config['music']).resolve()
    if not path.is_file():
        raise FileNotFoundError(f'音乐文件不存在: {path}')
    return path
