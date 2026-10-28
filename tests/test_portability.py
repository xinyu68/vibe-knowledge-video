import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PortabilityTests(unittest.TestCase):
    def test_no_machine_paths_in_repository_text(self):
        machine_path = re.compile(r'(?<![A-Za-z0-9])(?:[A-Za-z]:[\\/]|/(?:Users|home)/[^\s/]+/)')
        paths = [ROOT/name for name in ['README.md', 'AGENTS.md', 'vibe.py', 'vibe.ps1']]
        for name in ['docs', 'prompts', 'tools', 'templates', 'assets/music',
                     'videos/missing-planes', 'videos/phantom-jam']:
            paths.extend((ROOT/name).rglob('*'))
        issues = []
        for path in paths:
            if not path.is_file() or path.suffix not in {'.py', '.ps1', '.md', '.txt', '.json', '.html', '.js'}:
                continue
            if any(part in {'build', 'review', '__pycache__'} or part.startswith('build-')
                   for part in path.relative_to(ROOT).parts):
                continue
            for number, line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
                if machine_path.search(line):
                    issues.append(f'{path.relative_to(ROOT).as_posix()}:{number}')
        self.assertEqual([], issues, 'Repository contains machine-specific path literals')

    def test_project_relative_report_references(self):
        from tools.project import ROOT as project_root, project_reference
        self.assertEqual('assets/fonts/Lora.ttf', project_reference(project_root/'assets/fonts/Lora.ttf'))
        outside = project_root.parent/'explicit-user-input.mp3'
        self.assertEqual(str(outside.resolve()), project_reference(outside))

    def test_relocated_project_with_unicode_spaces_and_unrelated_cwd(self):
        for command in ['ffmpeg', 'ffprobe']:
            if not shutil.which(command):
                self.skipTest(f'Install {command} to run relocation integration checks')
        if importlib.util.find_spec('playwright') is None:
            self.skipTest('Install project requirements to run browser relocation checks')
        temporary = tempfile.TemporaryDirectory(prefix='vibe-relocation-')
        scratch = Path(temporary.name).resolve()
        intended_parent = Path(tempfile.gettempdir()).resolve()
        self.assertEqual(intended_parent, scratch.parent)
        try:
            relocated = scratch/'异机 工作区'/'knowledge-video'
            relocated.mkdir(parents=True)
            for name in ['vibe.py', 'vibe.ps1', 'requirements.txt']:
                shutil.copy2(ROOT/name, relocated/name)
            for name in ['tools', 'templates', 'assets']:
                shutil.copytree(ROOT/name, relocated/name, ignore=shutil.ignore_patterns('__pycache__'))
            example = relocated/'videos'/'missing-planes'
            example.mkdir(parents=True)
            for source in (ROOT/'videos/missing-planes').iterdir():
                if source.is_file():
                    shutil.copy2(source, example/source.name)
            unrelated = scratch/'unrelated working directory'
            unrelated.mkdir()
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'

            def cli(*arguments, expected=0):
                result = subprocess.run([sys.executable, str(relocated/'vibe.py'), *arguments],
                                        cwd=unrelated, env=env, capture_output=True,
                                        encoding='utf-8', timeout=180)
                self.assertEqual(expected, result.returncode, result.stdout+'\n'+result.stderr)
                return result.stdout

            cli('doctor')
            checked = json.loads(cli('check', 'missing-planes'))
            self.assertEqual(str(example), checked['video'])
            self.assertTrue(Path(checked['music']).is_relative_to(relocated))
            cli('new', 'narrated-topic', '--title', '配音新主题', '--topic', '独立故事', '--narrated')
            narrated = relocated/'videos/narrated-topic'
            narrated_config = json.loads((narrated/'film.json').read_text(encoding='utf-8'))
            self.assertFalse(narrated_config['production_ready'])
            self.assertEqual(-18, narrated_config['music_gain_db'])
            voice_plan = json.loads((narrated/narrated_config['narration']).read_text(encoding='utf-8'))
            self.assertEqual(('constant', 'zh-CN-YunjianNeural', []),
                             (voice_plan['music_mode'], voice_plan['voice'], voice_plan['cues']))
            cli('check', 'narrated-topic')
            cli('mix', 'narrated-topic', expected=1)
            cli('new', 'new-topic', '--title', '新的主题', '--topic', '异机复用检查')
            new_folder = relocated/'videos/new-topic'
            self.assertTrue((new_folder/'plan.js').is_file())
            self.assertEqual('新的主题', json.loads((new_folder/'plan.json').read_text(encoding='utf-8'))['title'])
            cli('preview', 'new-topic')
            audit = json.loads((new_folder/'build/review/layout_audit.json').read_text(encoding='utf-8'))
            self.assertEqual(0, audit['layout_issue_frames'])
            self.assertTrue((new_folder/'build/review/overview_1.jpg').is_file())
            cli('render', 'new-topic', '--start', '0', '--end', '3', '--name', 'portable-smoke', '--jobs', '1')
            probe = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                                    'stream=nb_frames,width,height', '-of', 'json',
                                    str(new_folder/'build/portable-smoke.mp4')],
                                   capture_output=True, encoding='utf-8', check=True)
            video = json.loads(probe.stdout)['streams'][0]
            self.assertEqual((1920, 1080, 3), (video['width'], video['height'], int(video['nb_frames'])))
            cli('mix', 'new-topic')
            metadata = json.loads((new_folder/'build/soundtrack.json').read_text(encoding='utf-8'))
            self.assertTrue(metadata['music'].startswith('assets/music/'))
            self.assertEqual('project_root', metadata['paths_relative_to'])
            with wave.open(str(new_folder/'build/soundtrack.wav')) as audio:
                self.assertAlmostEqual(159.25, audio.getnframes()/audio.getframerate(), places=3)
            if (ROOT/'videos/missing-planes/audio').is_dir():
                shutil.copytree(ROOT/'videos/missing-planes/audio', example/'audio')
                cli('mix', 'missing-planes')
                output = json.loads((example/'film.json').read_text(encoding='utf-8'))['output']
                voice_mix = json.loads((example/output/'soundtrack.json').read_text(encoding='utf-8'))
                self.assertEqual('zh-CN-YunjianNeural', voice_mix['narration']['voice'])
                self.assertEqual(29, voice_mix['narration']['cue_count'])
                self.assertEqual('constant', voice_mix['narration']['music_mode'])
                self.assertEqual((1., 1.), (voice_mix['narration']['music_envelope_min'],
                                           voice_mix['narration']['music_envelope_max']))
            if os.name == 'nt':
                wrapper = subprocess.run(['powershell', '-NoProfile', '-File', str(relocated/'vibe.ps1'),
                                          'check', 'new-topic'], cwd=unrelated, env=env,
                                         capture_output=True, encoding='utf-8', timeout=30)
                self.assertEqual(0, wrapper.returncode, wrapper.stdout+'\n'+wrapper.stderr)
                self.assertEqual(str(new_folder), json.loads(wrapper.stdout)['video'])
        finally:
            resolved_cleanup_target = Path(temporary.name).resolve()
            if resolved_cleanup_target != scratch or resolved_cleanup_target.parent != intended_parent:
                raise RuntimeError('Unexpected temporary test cleanup target')
            temporary.cleanup()


if __name__ == '__main__':
    unittest.main()
