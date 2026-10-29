"""Deterministic local Canvas renderer with source signatures and frame review."""

import argparse
import base64
import concurrent.futures
import functools
import hashlib
import http.server
import io
import json
import math
import re
import subprocess
import threading
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright
from .project import frame_index
from .runtime import browser_launch_choices

ROOT = OUT = HTTP_ROOT = ENTRY = None
FPS = 30
FRAMES = 0
WIDTH, HEIGHT = 1920, 1080
TIMES, SOURCE_NAMES, MOTION_RANGES = [], [], []
PAGE_INIT_LOCK = threading.Lock()


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def source_signature():
    digest = hashlib.sha256()
    for name in SOURCE_NAMES:
        if not (ROOT / name).is_file():
            raise FileNotFoundError(ROOT / name)
        digest.update(name.encode('utf-8'))
        digest.update((ROOT / name).read_bytes())
    return digest.hexdigest()


def server():
    srv = http.server.ThreadingHTTPServer(
        ('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(HTTP_ROOT)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f'http://127.0.0.1:{srv.server_port}/' + ENTRY.relative_to(HTTP_ROOT).as_posix()


def browser_page(playwright, url):
    # Serialize startup/font loading; frame drawing and encoding still run in parallel.
    with PAGE_INIT_LOCK:
        return _browser_page(playwright, url)


def _browser_page(playwright, url):
    launch_args = ['--disable-lcd-text', '--force-color-profile=srgb']
    failure = None
    for options in browser_launch_choices():
        try:
            browser = playwright.chromium.launch(**options, args=launch_args)
            break
        except Exception as error:
            failure = error
    else:
        raise failure
    page = browser.new_page(viewport={'width': WIDTH, 'height': HEIGHT}, device_scale_factor=1)
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    try:
        for attempt in range(2):
            try:
                page.goto(url, wait_until='load')
                page.wait_for_function('window.READY === true', timeout=60000, polling=100)
                page.wait_for_function(
                    'typeof window.render === "function" || typeof window.seek === "function"',
                    timeout=5000, polling=100)
                if errors:
                    raise RuntimeError('Page errors: ' + '; '.join(errors))
                return browser, page
            except Exception:
                if attempt:
                    raise
                errors.clear()
                print('Retrying local page and font initialization', flush=True)
    except Exception:
        browser.close()
        raise


def frame_bytes(page, seconds, kind='png'):
    data = page.evaluate('''({t,kind}) => {
        (window.render || window.seek)(t);
        const canvas = document.getElementById('stage');
        return canvas.toDataURL('image/' + kind, 0.98).split(',')[1];
    }''', {'t': seconds, 'kind': kind})
    return base64.b64decode(data)


def make_sheet(images, times, path, columns=3):
    if not images:
        return
    width = 640 if columns == 3 else 480
    height = width * 9 // 16
    sheet = Image.new('RGB', (width * columns, math.ceil(len(images) / columns) * (height + 30)), '#111a29')
    draw = ImageDraw.Draw(sheet)
    font_path = Path(__file__).resolve().parents[1] / 'assets' / 'fonts' / 'Lora.ttf'
    font = ImageFont.truetype(str(font_path), 20)
    for index, (image, seconds) in enumerate(zip(images, times)):
        x, y = index % columns * width, index // columns * (height + 30)
        sheet.paste(image.resize((width, height), Image.Resampling.LANCZOS), (x, y))
        draw.text((x + 12, y + height + 4), f'{seconds:.3f}s', font=font, fill='#e7edf6')
    sheet.save(path, quality=94)


def preview(times=None):
    dest = OUT / 'review'
    dest.mkdir(parents=True, exist_ok=True)
    times = list(TIMES if times is None else times)
    signature = source_signature()
    srv, url = server()
    entries, issues = [], []
    try:
        with sync_playwright() as playwright:
            browser, page = browser_page(playwright, url)
            try:
                if not page.evaluate('typeof window.audit === "function"'):
                    raise RuntimeError('window.audit(t) is required for layout review')
                for seconds in times:
                    seconds = frame_index(seconds, FPS, FRAMES) / FPS
                    filename = f'{seconds:010.6f}.png'
                    (dest / filename).write_bytes(frame_bytes(page, seconds))
                    result = page.evaluate('(t) => window.audit(t)', seconds)
                    entries.append({'time': seconds, 'file': filename, 'audit': result})
                    if result:
                        issues.append({'time': seconds, 'audit': result})
                transition_ranges = MOTION_RANGES
                strips = []
                for start, end, name in transition_ranges:
                    moments = [start + (end - start) * index / 7 for index in range(8)]
                    images = [Image.open(io.BytesIO(frame_bytes(page, t))).convert('RGB') for t in moments]
                    filename = f'transition_{name}.jpg'
                    make_sheet(images, moments, dest / filename, 4)
                    strips.append({'file': filename, 'times': moments})
            finally:
                browser.close()
    finally:
        srv.shutdown()
        srv.server_close()
    images = [Image.open(dest / entry['file']).convert('RGB') for entry in entries]
    for index in range(math.ceil(len(images) / 12)):
        make_sheet(images[index * 12:(index + 1) * 12], times[index * 12:(index + 1) * 12],
                   dest / f'overview_{index + 1}.jpg')
    report = {'source_sha256': signature, 'sampled_frames': len(entries),
              'layout_issue_frames': len(issues), 'issues': issues, 'frames': entries,
              'transition_strips': strips,
              'limitations': 'Geometry audit is not a visual overlap or legibility judgment; images require review.'}
    (dest / 'layout_audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'PREVIEW COMPLETE: {len(entries)} source frames; {len(issues)} audit issue frames', flush=True)


def part_path(name, start, end, index):
    return OUT / f'{name}_{start:05d}_{end:05d}_part_{index:02d}.mp4'


def part(start, end, index, url, name, signature):
    target = part_path(name, start, end, index)
    meta_path = target.with_suffix('.json')
    if meta_path.exists():
        meta_path.unlink()
    with sync_playwright() as playwright:
        browser, page = browser_page(playwright, url)
        command = ['ffmpeg', '-v', 'error', '-y', '-f', 'image2pipe', '-vcodec', 'mjpeg',
                   '-framerate', str(FPS), '-i', '-', '-an', '-c:v', 'libx264', '-preset',
                   'fast', '-crf', '17', '-threads', '2', '-pix_fmt', 'yuv420p',
                   '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace',
                   'bt709', '-movflags', '+faststart', str(target)]
        encoder = subprocess.Popen(command, stdin=subprocess.PIPE)
        begun = time.monotonic()
        try:
            for frame in range(start, end):
                encoder.stdin.write(frame_bytes(page, frame / FPS, 'jpeg'))
                if (frame - start) % 300 == 0:
                    print(f'{name} part {index}: {frame - start}/{end - start}, {time.monotonic() - begun:.1f}s', flush=True)
            encoder.stdin.close()
            if encoder.wait() != 0:
                raise RuntimeError(f'FFmpeg failed for {target.name}')
        except BaseException:
            if encoder.poll() is None:
                encoder.kill()
                encoder.wait()
            raise
        finally:
            browser.close()
    metadata = {'source_sha256': signature, 'start': start, 'end': end, 'frames': end - start,
                'fps': FPS, 'width': WIDTH, 'height': HEIGHT}
    meta_path.write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    return target


def reusable(target, start, end, signature):
    try:
        metadata = json.loads(target.with_suffix('.json').read_text(encoding='utf-8'))
        if metadata['source_sha256'] != signature or metadata['start'] != start or metadata['end'] != end:
            return False
        result = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                                 '-show_entries', 'stream=nb_frames,width,height,avg_frame_rate',
                                 '-of', 'json', str(target)], check=True, capture_output=True, encoding='utf-8')
        video = json.loads(result.stdout)['streams'][0]
        return (int(video.get('nb_frames', 0)) == end - start and video['width'] == WIDTH
                and video['height'] == HEIGHT and video['avg_frame_rate'] == '30/1')
    except (OSError, ValueError, KeyError, IndexError, subprocess.SubprocessError):
        return False


def render(start, end, jobs, name, resume=False, force=()):
    if not 0 <= start < end <= FRAMES:
        raise ValueError(f'Require 0 <= start < end <= {FRAMES}')
    if not re.fullmatch(r'[A-Za-z0-9_-]+', name):
        raise ValueError('Render name may contain ASCII letters, digits, underscore and hyphen')
    if not 1 <= jobs <= 16:
        raise ValueError('jobs must be between 1 and 16')
    jobs = min(jobs, end - start)
    cuts = [round(start + (end - start) * index / jobs) for index in range(jobs + 1)]
    signature = source_signature()
    srv, url = server()
    paths = []
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
            futures = []
            for index in range(jobs):
                first, last = cuts[index], cuts[index + 1]
                target = part_path(name, first, last, index)
                paths.append(target)
                if resume and index not in force and reusable(target, first, last, signature):
                    print(f'Reuse {target.name}: verified source and frame count', flush=True)
                else:
                    futures.append(pool.submit(part, first, last, index, url, name, signature))
            for future in futures:
                future.result()
    finally:
        srv.shutdown()
        srv.server_close()
    listing = OUT / f'{name}.concat.txt'
    # MP4 format durations can be rounded to milliseconds. Exact frame durations
    # keep segment boundaries on the frame grid when the concat demuxer joins them.
    listing.write_text(''.join(
        "file '" + path.as_posix().replace("'", "'\\''") + "'\n"
        + f'duration {(cuts[index + 1] - cuts[index]) / FPS:.9f}\n'
        for index, path in enumerate(paths)), encoding='utf-8')
    target = OUT / f'{name}.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i',
                    str(listing), '-c', 'copy', '-movflags', '+faststart', str(target)], check=True)
    (OUT / f'{name}.render.json').write_text(json.dumps({
        'source_sha256': signature, 'start': start, 'end': end, 'frames': end - start,
        'parts': [path.name for path in paths], 'output': target.name}, indent=2), encoding='utf-8')
    print('VIDEO READY', str(target), flush=True)




def configure(project_root, video_dir, config, plan):
    global ROOT, OUT, HTTP_ROOT, ENTRY, FPS, FRAMES, TIMES, SOURCE_NAMES, MOTION_RANGES
    ROOT = video_dir
    HTTP_ROOT = project_root
    ENTRY = video_dir / config['entry']
    OUT = video_dir / config.get('output', 'build')
    OUT.mkdir(parents=True, exist_ok=True)
    FPS, FRAMES = plan['fps'], plan['frames']
    TIMES = config.get('preview_times', [0, 1, plan['duration'] / 2, plan['duration'] - 1])
    SOURCE_NAMES = config['sources'] + ['film.json', '../../assets/fonts/NotoSerifSC-VF.ttf', '../../assets/fonts/Lora.ttf', '../../assets/fonts/Lora-Italic.ttf']
    MOTION_RANGES = config.get('motion_ranges', [])
