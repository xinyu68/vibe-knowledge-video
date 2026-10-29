"""Local diagnostics with explicit online-synthesis verification."""

from datetime import datetime, timezone
import importlib.metadata
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

from .project import ROOT
from .runtime import browser_launch_choices


def diagnose(online=False):
    checks, errors, versions = {}, {}, {}
    result = {'python': sys.executable, 'python_version': sys.version.split()[0],
              'project': str(ROOT), 'checks': checks, 'errors': errors, 'versions': versions,
              'online_synthesis': 'not_tested'}
    checks['python_3_10_or_newer'] = sys.version_info >= (3, 10)
    for module, package in [('numpy', 'numpy'), ('PIL', 'Pillow'), ('playwright', 'playwright'), ('edge_tts', 'edge-tts')]:
        checks[module] = importlib.util.find_spec(module) is not None
        if checks[module]:
            versions[package] = importlib.metadata.version(package)
        else:
            errors[module] = 'Run python bootstrap.py to install project dependencies'
    for command in ('ffmpeg', 'ffprobe'):
        path = shutil.which(command)
        checks[command] = False
        if path:
            try:
                completed = subprocess.run([path, '-version'], capture_output=True, text=True, timeout=20)
                checks[command] = completed.returncode == 0
                versions[command] = completed.stdout.splitlines()[0] if completed.stdout else 'failed to start'
            except (OSError, subprocess.SubprocessError) as error:
                errors[command] = str(error)
        if not checks[command]:
            errors.setdefault(command, 'Run python bootstrap.py; FFmpeg and FFprobe must both be executable')
    checks['browser'] = False
    if checks['playwright']:
        from playwright.sync_api import sync_playwright
        try:
            with sync_playwright() as playwright:
                failures = []
                for kwargs in browser_launch_choices():
                    try:
                        browser = playwright.chromium.launch(**kwargs)
                        browser.close()
                        checks['browser'] = True
                        result['browser'] = 'chrome' if kwargs else 'playwright-chromium'
                        break
                    except Exception as error:
                        failures.append(str(error).splitlines()[0])
                if not checks['browser']:
                    errors['browser'] = failures
        except Exception as error:
            errors['browser'] = str(error).splitlines()[0]
    for filename in ('NotoSerifSC-VF.ttf', 'Lora.ttf', 'Lora-Italic.ttf'):
        checks[filename] = (ROOT / 'assets/fonts' / filename).is_file()
    checks['default_music'] = any((ROOT / 'assets/music').glob('*.mp3'))
    checks['creation_skill'] = (ROOT / '.agents/skills/vibe-video/SKILL.md').is_file()
    result['local_environment_ok'] = all(checks.values())
    if online:
        if not checks['edge_tts'] or not checks['ffmpeg']:
            checks['online_synthesis'] = False
            result['online_synthesis'] = 'blocked_by_local_dependencies'
        else:
            from .edge_voice import synthesize_edge
            folder = ROOT / '.local/doctor'
            target = folder / f'voice-{uuid.uuid4().hex[:8]}.wav'
            try:
                details = synthesize_edge('配音连接测试。', target)
                checks['online_synthesis'] = True
                result['online_synthesis'] = 'passed'
                result['voice_probe'] = {'file': target.relative_to(ROOT).as_posix(), **details}
            except Exception as error:
                checks['online_synthesis'] = False
                result['online_synthesis'] = 'failed'
                errors['online_synthesis'] = str(error)
    result['ok'] = all(checks.values())
    result['checked_at'] = datetime.now(timezone.utc).isoformat()
    result['next_step'] = ('python vibe.py self-test' if result['local_environment_ok']
                           else 'python bootstrap.py')
    return result
