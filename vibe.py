"""Entry point for the local music-driven knowledge-video project."""

import argparse
import importlib.util
import json
import math
import shutil
import subprocess
import sys

from tools.project import ROOT, load, music_path, read_json, video_path, write_json

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')


def doctor():
    result = {'python': sys.executable, 'python_version': sys.version.split()[0],
              'project': str(ROOT), 'checks': {}}
    result['checks']['python_3_10_or_newer'] = sys.version_info >= (3, 10)
    for module in ['numpy', 'PIL', 'playwright']:
        result['checks'][module] = importlib.util.find_spec(module) is not None
    for command in ['ffmpeg', 'ffprobe']:
        result['checks'][command] = shutil.which(command) is not None
    if result['checks']['playwright']:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as playwright:
            errors = []
            for kwargs in [{'channel': 'chrome'}, {}]:
                try:
                    browser = playwright.chromium.launch(**kwargs)
                    result['browser'] = 'chrome' if kwargs else 'playwright-chromium'
                    browser.close()
                    result['checks']['browser'] = True
                    break
                except Exception as error:
                    errors.append(str(error).splitlines()[0])
            else:
                result['checks']['browser'] = False
                result['browser_errors'] = errors
    for name in ['NotoSerifSC-VF.ttf', 'Lora.ttf', 'Lora-Italic.ttf']:
        result['checks'][name] = (ROOT/'assets/fonts'/name).is_file()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not all(result['checks'].values()):
        raise SystemExit(1)


def create(slug, title, topic, narrated=False):
    folder = video_path(slug)
    if folder.exists():
        raise FileExistsError(f'视频目录已存在，迭代时请直接编辑: {folder}')
    shutil.copytree(ROOT/'templates/episode', folder)
    config = read_json(folder/'film.json')
    config['title'], config['topic'] = title, topic or title
    if narrated:
        config['narration'] = 'narration.json'
        config['music_gain_db'] = -18
        shutil.copy2(ROOT/'templates/narration.json', folder/'narration.json')
    write_json(folder/'film.json', config)
    plan = read_json(folder/'plan.json')
    plan['title'] = title
    write_json(folder/'plan.json', plan)
    for path in folder.glob('*.md'):
        path.write_text(path.read_text(encoding='utf-8').replace('{{主题}}', topic or title), encoding='utf-8')
    load(slug)
    next_step = '；填写 narration.json 后合成配音并实测入窗' if narrated else ''
    print(f'已创建视频骨架: {folder}\n下一步填写 brief.md、research.md、storyboard.md，并编写 scenes.js{next_step}；骨架不是成片。')


def configured(slug):
    from tools import render
    folder, config, plan = load(slug)
    render.configure(ROOT, folder, config, plan)
    return render, folder, config, plan


def require_review(render, config):
    if not config.get('production_ready'):
        raise ValueError('production_ready=false：先完成选题、分镜、字幕和主体动作，再渲染完整成片；可先渲染短片段调试')
    audit = read_json(render.OUT/'review/layout_audit.json')
    if audit['source_sha256'] != render.source_signature() or audit['layout_issue_frames']:
        raise ValueError('先对当前源码运行 preview 并修复文字越界，再进行完整渲染')


def main():
    parser = argparse.ArgumentParser(description='本地知识动画视频工程：音乐为主时钟，支持中文 AI 配音与稳定配乐')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('doctor', help='检查 Python、依赖、浏览器与 FFmpeg')
    sub.add_parser('list', help='列出视频项目')
    new = sub.add_parser('new', help='创建待编写的独立视频骨架')
    new.add_argument('slug')
    new.add_argument('--title', required=True)
    new.add_argument('--topic')
    new.add_argument('--narrated', action='store_true', help='创建中文配音骨架，配乐固定增益；填写旁白后再合成')
    music = sub.add_parser('analyze-music', help='解码音轨并输出 10ms RMS 数据，不自动认定重拍')
    music.add_argument('slug')
    speech = sub.add_parser('narrate', help='用 ttsCN 按cue合成旁白，缓存语义段落音频并实测时间轴')
    speech.add_argument('slug')
    speech.add_argument('--tts-cli', required=True, help='本机安装的 ttsCN scripts/tts.py 路径')
    for name in ['preview', 'render', 'mix', 'finalize', 'check', 'serve']:
        item = sub.add_parser(name)
        item.add_argument('slug')
        if name == 'preview':
            item.add_argument('--times', help='逗号分隔的额外抽帧秒数；默认按 film.json 检查')
        elif name == 'render':
            item.add_argument('--start', type=int, default=0)
            item.add_argument('--end', type=int)
            item.add_argument('--jobs', type=int, default=4)
            item.add_argument('--name', default='picture')
            item.add_argument('--resume', action='store_true')
        elif name == 'serve':
            item.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    if args.command == 'doctor':
        return doctor()
    if args.command == 'list':
        for path in sorted((ROOT/'videos').glob('*/film.json')):
            cfg = read_json(path)
            state = '测试骨架' if cfg.get('test_only') else ('内容已完成' if cfg.get('production_ready') else '制作骨架')
            print(f'{path.parent.name}\t{cfg["title"]}\t'+state)
        return
    if args.command == 'new':
        return create(args.slug, args.title, args.topic, args.narrated)
    folder, config, plan = load(args.slug)
    if args.command == 'narrate':
        from tools.narration import synthesize
        synthesize(folder, config, plan, args.tts_cli)
        return
    if args.command == 'check':
        return print(json.dumps({'video': str(folder), 'duration': plan['duration'], 'frames': plan['frames'],
                                 'production_ready': config.get('production_ready'), 'subtitles': len(plan.get('subtitles', [])),
                                 'music': str(music_path(folder, config)), 'status': 'configuration_valid'}, ensure_ascii=False, indent=2))
    if args.command == 'serve':
        print(f'本地预览 http://127.0.0.1:{args.port}/videos/{args.slug}/player.html', flush=True)
        return subprocess.run([sys.executable, '-m', 'http.server', str(args.port), '--bind', '127.0.0.1', '--directory', str(ROOT)], check=True)
    if args.command == 'analyze-music':
        from tools.mix import analyze
        return analyze(music_path(folder, config), folder/'build/music-analysis')
    if args.command == 'mix':
        from tools.mix import mix
        return mix(folder, config, plan)
    render, folder, config, plan = configured(args.slug)
    if args.command == 'preview':
        times = None
        if args.times:
            times = sorted(set(config.get('preview_times', []) + [float(x) for x in args.times.split(',')]))
            if any(not math.isfinite(t) or not 0 <= t < plan['duration'] for t in times):
                raise ValueError('所有抽帧时间须位于片内')
        render.preview(times)
        if read_json(render.OUT/'review/layout_audit.json')['layout_issue_frames']:
            raise SystemExit(2)
        return
    if args.command == 'render':
        end = plan['frames'] if args.end is None else args.end
        complete = args.start == 0 and end == plan['frames']
        if complete:
            require_review(render, config)
        elif args.name == 'picture':
            raise ValueError('短片段使用 --name smoke 等名称，保留 picture.mp4 给完整画面')
        return render.render(args.start, end, args.jobs, args.name, args.resume)
    if args.command == 'finalize':
        require_review(render, config)
        from tools.mix import mix
        from tools.finalize import finalize
        mix(folder, config, plan)
        return finalize(folder, config, plan, render.source_signature())


if __name__ == '__main__':
    try:
        main()
    except (ValueError, FileNotFoundError, FileExistsError, RuntimeError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        raise SystemExit(1)
