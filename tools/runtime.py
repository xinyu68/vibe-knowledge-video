"""Project-local executables, without modifying the user's persistent PATH."""

import os
from pathlib import Path


def configure_paths(root=None):
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    directory = root / '.local/ffmpeg/bin'
    suffix = '.exe' if os.name == 'nt' else ''
    if all((directory / (name + suffix)).is_file() for name in ('ffmpeg', 'ffprobe')):
        entries = os.environ.get('PATH', '').split(os.pathsep)
        if str(directory) not in entries:
            os.environ['PATH'] = os.pathsep.join([str(directory), *entries])
    browsers = root / '.local/browsers'
    if browsers.is_dir():
        os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH', str(browsers))


def browser_launch_choices():
    selected = os.environ.get('VIBE_BROWSER', 'auto')
    if selected == 'chromium':
        return [{}]
    if selected == 'chrome':
        return [{'channel': 'chrome'}]
    if selected != 'auto':
        raise ValueError('VIBE_BROWSER must be auto, chrome or chromium')
    return [{'channel': 'chrome'}, {}]
