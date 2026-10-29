"""Prepare the local video environment, then verify it with a newly voiced ten-second clip."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import venv
import zipfile

from tools.runtime import configure_paths

ROOT = Path(__file__).resolve().parent
# Release build listed by the Windows distributor linked from ffmpeg.org/download.html.
FFMPEG_URL = 'https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-9.0.2-essentials_build.zip'
FFMPEG_SHA256 = '60f467265b1e312373dbcd92200c2618a74850f98d3d078e94296bb3fa2047ba'


def executable_works(name):
    command = shutil.which(name)
    if not command:
        return False
    try:
        return subprocess.run([command, '-version'], capture_output=True, timeout=20).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def install_windows_ffmpeg(root):
    local = root / '.local'
    local.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='ffmpeg-download-', dir=local) as temporary:
        archive = Path(temporary) / 'ffmpeg.zip'
        digest = hashlib.sha256()
        print('Downloading the verified Windows FFmpeg release into this project...', flush=True)
        with urllib.request.urlopen(FFMPEG_URL, timeout=30) as response, archive.open('wb') as stream:
            downloaded = 0
            for block in iter(lambda: response.read(1024 * 1024), b''):
                digest.update(block)
                stream.write(block)
                downloaded += len(block)
                if downloaded // (16 * 1024 * 1024) > (downloaded - len(block)) // (16 * 1024 * 1024):
                    print(f'FFmpeg download: {downloaded // (1024 * 1024)} MiB', flush=True)
        if digest.hexdigest() != FFMPEG_SHA256:
            raise RuntimeError('FFmpeg archive checksum mismatch; no executable was installed')
        destination = local / 'ffmpeg/bin'
        destination.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive) as package:
            # Copy only exact required basenames, never extract arbitrary archive paths.
            for name in ('ffmpeg.exe', 'ffprobe.exe'):
                matches = [entry for entry in package.infolist()
                           if not entry.is_dir() and entry.filename.endswith('/bin/' + name)]
                if len(matches) != 1:
                    raise RuntimeError('Unexpected FFmpeg package contents: ' + name)
                with package.open(matches[0]) as source, (destination / name).open('wb') as target:
                    shutil.copyfileobj(source, target)
            for entry in package.infolist():
                if Path(entry.filename).name.lower() in ('license', 'license.txt'):
                    (destination.parent / 'LICENSE.txt').write_bytes(package.read(entry))
                    break
        (destination.parent / 'download.json').write_text(json.dumps({
            'url': FFMPEG_URL, 'sha256': FFMPEG_SHA256, 'version': '9.0.2'}, indent=2) + '\n', encoding='utf-8')
    configure_paths(root)


def prepare_ffmpeg(root):
    configure_paths(root)
    if all(executable_works(name) for name in ('ffmpeg', 'ffprobe')):
        return 'existing'
    if platform.system() == 'Windows' and platform.machine().lower() in ('amd64', 'x86_64'):
        install_windows_ffmpeg(root)
    else:
        raise RuntimeError('Install FFmpeg and FFprobe, then rerun bootstrap.py. '
                           'macOS: brew install ffmpeg. Debian/Ubuntu: sudo apt install ffmpeg. '
                           'Other systems: https://ffmpeg.org/download.html')
    if not all(executable_works(name) for name in ('ffmpeg', 'ffprobe')):
        raise RuntimeError('Installed FFmpeg could not start; inspect .local/ffmpeg/bin')
    return 'project-local'


def bootstrap(skip_self_test=False):
    if sys.version_info < (3, 10):
        raise RuntimeError('Install Python 3.10 or newer before running bootstrap.py')
    environment = ROOT / '.venv'
    python = environment / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    print('[1/5] Preparing project virtual environment', flush=True)
    if not python.is_file():
        if environment.exists() and any(environment.iterdir()):
            raise RuntimeError('Existing .venv is incomplete or from another platform. Rename it and rerun bootstrap.py.')
        venv.EnvBuilder(with_pip=True).create(environment)
    try:
        subprocess.run([str(python), '-c', 'import sys; assert sys.version_info >= (3, 10)'], check=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as error:
        raise RuntimeError('Existing .venv cannot run here. Rename it and rerun bootstrap.py; do not copy virtual environments between computers.') from error
    print('[2/5] Installing rendering and built-in voice dependencies', flush=True)
    subprocess.run([str(python), '-m', 'pip', 'install', '-r', str(ROOT / 'requirements.txt')], check=True)
    print('[3/5] Checking FFmpeg and installing the local browser', flush=True)
    prepare_ffmpeg(ROOT)
    runtime = os.environ.copy()
    runtime['PLAYWRIGHT_BROWSERS_PATH'] = str(ROOT / '.local/browsers')
    runtime['VIBE_BROWSER'] = 'chromium'
    subprocess.run([str(python), '-m', 'playwright', 'install', 'chromium'], env=runtime, check=True)
    print('[4/5] Checking local dependencies', flush=True)
    subprocess.run([str(python), str(ROOT / 'vibe.py'), 'doctor'], cwd=ROOT, env=runtime, check=True)
    if skip_self_test:
        print('[5/5] Self-test skipped: online synthesis and end-to-end production remain unverified.', flush=True)
    else:
        print('[5/5] Synthesizing new narration and exporting a ten-second test', flush=True)
        subprocess.run([str(python), str(ROOT / 'vibe.py'), 'self-test'], cwd=ROOT, env=runtime, check=True)
    print('Environment prepared. Open this project in Codex and use $vibe-video.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skip-self-test', action='store_true', help='Install only; do not claim online voice or full pipeline verification')
    args = parser.parse_args()
    try:
        bootstrap(args.skip_self_test)
    except (OSError, RuntimeError, subprocess.SubprocessError, zipfile.BadZipFile) as error:
        print(f'Bootstrap stopped: {error}\nFix the reported step and rerun the same command; completed installations can be reused.', file=sys.stderr)
        raise SystemExit(1)
