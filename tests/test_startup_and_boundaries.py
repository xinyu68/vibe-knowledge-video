import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch
import wave
import zipfile

import numpy as np

import bootstrap
from tools import mix, narration
from tools import finalize as finalizer
from tools.doctor import diagnose
from tools.edge_voice import synthesize_edge
from tools.project import frame_index, write_json


class AudioBoundaryTests(unittest.TestCase):
    def test_subframe_music_differences_are_aligned_without_changing_voice_samples(self):
        with tempfile.TemporaryDirectory(prefix='vibe-mix-boundary-') as temporary:
            folder = Path(temporary)
            (folder / 'music.wav').write_bytes(b'input hash fixture')
            config = {'music': 'music.wav', 'narration': 'narration.json', 'ambience_gain': 0}
            plan = {'duration': 1.0}
            voice = np.linspace(-.1, .1, mix.SR, dtype=np.float32)
            report = {'music_mode': 'constant', 'voice': 'test', 'cues': [], 'speech_lufs': -18, 'duck_db': 0}
            for delta in (-1000, -1, 0, 1, 1000):
                with self.subTest(delta=delta), patch.object(mix, 'decode', return_value=np.zeros((mix.SR + delta, 2), dtype=np.float32)), \
                        patch.object(narration, 'assemble', return_value=(voice.copy(), report)):
                    target = mix.mix(folder, config, plan)
                    with wave.open(str(target), 'rb') as stream:
                        self.assertEqual(mix.SR, stream.getnframes())
                        samples = np.frombuffer(stream.readframes(mix.SR), dtype='<i2').reshape(-1, 2)
                    np.testing.assert_allclose(samples[:-3000, 0] / 32767, voice[:-3000], atol=1 / 32767)
                    metadata = json.loads((folder / 'build/soundtrack.json').read_text(encoding='utf-8'))
                    self.assertEqual(-delta, metadata['music_alignment_samples'])
            with patch.object(mix, 'decode', return_value=np.zeros((mix.SR + 2000, 2), dtype=np.float32)):
                with self.assertRaises(ValueError):
                    mix.mix(folder, config, plan)


class FrameBoundaryTests(unittest.TestCase):
    def test_last_review_time_maps_to_a_real_frame(self):
        self.assertEqual(299, frame_index(9.99, 30, 300))
        self.assertEqual(0, frame_index(0, 30, 300))
        self.assertEqual(4777, frame_index(159.2499, 30, 4778))
        for seconds in (-1, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                frame_index(seconds, 30, 300)

    def test_real_final_encoding_extracts_last_frame_and_removes_stale_images(self):
        with tempfile.TemporaryDirectory(prefix='vibe-final-frame-') as temporary:
            folder = Path(temporary)
            out = folder / 'build'
            review = out / 'review'
            review.mkdir(parents=True)
            plan = {'duration': 10, 'fps': 30, 'frames': 300, 'impact_frame': 150}
            config = {'production_ready': True, 'preview_times': [0, 9.99]}
            write_json(out / 'picture.render.json', {'start': 0, 'frames': 300, 'source_sha256': 'fixture'})
            write_json(review / 'layout_audit.json', {'source_sha256': 'fixture', 'layout_issue_frames': 0})
            (review / 'encoded_003.png').write_bytes(b'stale image must disappear')
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                            'color=c=gray:s=1920x1080:r=30', '-frames:v', '300',
                            '-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p',
                            str(out / 'picture.mp4')], check=True)
            t = np.arange(10 * mix.SR) / mix.SR
            narration.save_wave(out / 'soundtrack.wav', .2 * np.sin(2 * np.pi * (220 * t + 15 * t * t)))
            # This fixture exercises real codec/frame extraction. The separate visual-review
            # contract tests cover creative review; no real episode is being approved here.
            with patch.object(finalizer, 'visual_source_signature', return_value='fixture'), \
                    patch.object(finalizer, 'require_visual_review', return_value={
                        'ok': True, 'status': 'not_applicable', 'scope': 'technical_fixture'}):
                finalizer.finalize(folder, config, plan, 'fixture')
            report = json.loads((review / 'validation.json').read_text(encoding='utf-8'))
            self.assertTrue(report['all_technical_checks_pass'])
            self.assertEqual([0, 299], [entry['frame'] for entry in report['encoded_frames']])
            self.assertTrue((review / 'encoded_002.png').is_file())
            self.assertFalse((review / 'encoded_003.png').exists())


class BuiltinNarrationTests(unittest.TestCase):
    def test_builtin_default_validates_cache_and_keeps_external_cli_compatibility(self):
        with tempfile.TemporaryDirectory(prefix='vibe-voice-cache-') as temporary:
            folder = Path(temporary)
            data = {'backend': 'edge', 'voice': 'zh-CN-YunjianNeural', 'rate': '+0%',
                    'music_mode': 'constant', 'cues': [{'id': 'p1', 'text': '测试', 'start': 0, 'end': 2}]}
            config, plan = {'narration': 'narration.json'}, {'duration': 2}
            write_json(folder / 'narration.json', data)

            def generate(text, target, voice, rate):
                target.write_bytes(b'new waveform')
                return {'synthesis_adapter': 'builtin-edge', 'word_boundaries': [{'text': text, 'offset_sec': 0, 'duration_sec': 1}]}

            with patch('tools.edge_voice.synthesize_edge', side_effect=generate) as synth, \
                    patch.object(narration, 'assemble', return_value=('track', {})):
                narration.synthesize(folder, config, plan)
                narration.synthesize(folder, config, plan)
                self.assertEqual(1, synth.call_count)
                (folder / 'audio/narration/p1/source.wav').write_bytes(b'corrupted cache')
                narration.synthesize(folder, config, plan)
                self.assertEqual(2, synth.call_count)
                metadata = json.loads((folder / 'audio/narration/p1/source.json').read_text(encoding='utf-8'))
                self.assertEqual('builtin-edge', metadata['synthesis_adapter'])
                self.assertEqual('测试', metadata['word_boundaries'][0]['text'])
                data['cues'][0]['text'] = 'Changed paragraph'
                write_json(folder / 'narration.json', data)
                cli = folder / 'external.py'
                cli.write_text('# stub', encoding='utf-8')
                def external(command, **kwargs):
                    Path(command[3]).write_bytes(b'external waveform')
                    return Mock(returncode=0, stdout=json.dumps({'ok': True, 'data': {}}))
                with patch.object(narration.subprocess, 'run', side_effect=external):
                    narration.synthesize(folder, config, plan, cli)
                self.assertEqual(2, synth.call_count)

    def test_builtin_adapter_converts_real_audio_and_retains_word_boundaries(self):
        import edge_tts
        with tempfile.TemporaryDirectory(prefix='vibe-edge-stream-') as temporary:
            folder = Path(temporary)
            encoded = subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                                      'sine=frequency=440:duration=0.3', '-f', 'mp3', '-'],
                                     capture_output=True, check=True).stdout
            class Communication:
                async def stream(self):
                    yield {'type': 'WordBoundary', 'text': '测试', 'offset': 500000, 'duration': 2000000}
                    yield {'type': 'audio', 'data': encoded}
            target = folder / 'voice.wav'
            with patch.object(edge_tts, 'Communicate', return_value=Communication()) as request:
                details = synthesize_edge('测试', target)
                self.assertEqual('WordBoundary', request.call_args.kwargs['boundary'])
            self.assertEqual(.05, details['word_boundaries'][0]['offset_sec'])
            with wave.open(str(target), 'rb') as audio:
                self.assertEqual((1, 44100, 2), (audio.getnchannels(), audio.getframerate(), audio.getsampwidth()))
            previous = target.read_bytes()
            with patch.object(edge_tts, 'Communicate', side_effect=RuntimeError('offline')):
                with self.assertRaisesRegex(RuntimeError, 'existing cache is preserved'):
                    synthesize_edge('new', target)
            self.assertEqual(previous, target.read_bytes())


class InstallationTests(unittest.TestCase):
    def test_verified_package_copies_only_required_binaries_and_rejects_bad_checksum(self):
        package = io.BytesIO()
        with zipfile.ZipFile(package, 'w') as archive:
            archive.writestr('ffmpeg/bin/ffmpeg.exe', b'ffmpeg')
            archive.writestr('ffmpeg/bin/ffprobe.exe', b'ffprobe')
            archive.writestr('ffmpeg/LICENSE', b'license')
            archive.writestr('../../escape.exe', b'must not be extracted')
        contents = package.getvalue()
        with tempfile.TemporaryDirectory(prefix='vibe-install-') as temporary:
            root = Path(temporary)
            with patch.object(bootstrap.urllib.request, 'urlopen', return_value=io.BytesIO(contents)), \
                    patch.object(bootstrap, 'FFMPEG_SHA256', 'invalid'):
                with self.assertRaisesRegex(RuntimeError, 'checksum'):
                    bootstrap.install_windows_ffmpeg(root)
            self.assertFalse((root / '.local/ffmpeg/bin/ffmpeg.exe').exists())
            with patch.object(bootstrap.urllib.request, 'urlopen', return_value=io.BytesIO(contents)), \
                    patch.object(bootstrap, 'FFMPEG_SHA256', hashlib.sha256(contents).hexdigest()), \
                    patch.object(bootstrap, 'configure_paths'):
                bootstrap.install_windows_ffmpeg(root)
            self.assertEqual(b'ffprobe', (root / '.local/ffmpeg/bin/ffprobe.exe').read_bytes())
            self.assertFalse((root / 'escape.exe').exists())

    def test_doctor_offline_does_not_claim_online_tts_was_checked(self):
        with patch('tools.edge_voice.synthesize_edge') as synth:
            result = diagnose()
            self.assertEqual('not_tested', result['online_synthesis'])
            synth.assert_not_called()
        with patch('tools.edge_voice.synthesize_edge', side_effect=RuntimeError('network unavailable')):
            result = diagnose(online=True)
            self.assertFalse(result['ok'])
            self.assertEqual('failed', result['online_synthesis'])


if __name__ == '__main__':
    unittest.main()
