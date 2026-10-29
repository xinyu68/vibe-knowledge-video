import copy
import math
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import wave

import numpy as np

from tools import video_review as quality
from tools.narration import cue_signature
from tools.project import write_json


def shot(sid, start, end, **changes):
    value = {'id': sid, 'start': start, 'end': end,
             'scene': 'night queue', 'subject': 'ticket', 'composition': 'close-up',
             'cause': 'waiting time increases', 'action': 'hand pulls ticket back',
             'result': 'person stays despite the delay', 'new_information': 'past time changes the choice',
             'transition': 'ticket edge becomes the next timeline',
             'repetition_reason': '', 'narration_ids': []}
    return {**value, **changes}


def wave_file(path, duration):
    path.parent.mkdir(parents=True, exist_ok=True)
    rate = 44100
    tone = .15 * np.sin(np.arange(round(duration * rate)) * 2 * np.pi * 230 / rate)
    with wave.open(str(path), 'wb') as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(rate)
        stream.writeframes(np.rint(tone * 32767).astype('<i2').tobytes())


class ShotContractTests(unittest.TestCase):
    def setUp(self):
        self.plan = {'duration': 159.25, 'fps': 30, 'frames': 4778, 'impact_frame': 511}
        self.shots = [shot('opening', 0, 17.033333333, narration_ids=['p1']),
                      shot('mechanism', 17.033333333, 159.25, subject='two future routes', composition='wide')]

    def test_full_music_coverage_and_music_only_shot_are_valid(self):
        report = quality.validate_shots({'shots': self.shots}, self.plan, {'p1'})
        self.assertTrue(report['ok'], report)
        self.assertEqual([], report['warnings'])

    def test_repeated_subject_is_a_review_warning_not_a_failure(self):
        self.shots[1]['subject'] = self.shots[0]['subject']
        self.shots[1]['repetition_reason'] = 'return to the opening with a different decision'
        report = quality.validate_shots(self.shots, self.plan)
        self.assertTrue(report['ok'])
        self.assertEqual('similar_adjacent_view', report['warnings'][0]['type'])

    def test_timing_and_event_failures_cannot_hide_in_descriptions(self):
        cases = [('start', 18), ('start', 16), ('end', 159), ('end', float('nan')),
                 ('start', False), ('cause', '  '), ('new_information', ''),
                 ('id', 'opening'), ('narration_ids', ['unknown'])]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                changed = copy.deepcopy(self.shots)
                changed[1][field] = value
                self.assertFalse(quality.validate_shots(changed, self.plan, {'p1'})['ok'])

    def test_action_samples_and_impact_neighbors_are_on_the_frame_grid(self):
        samples = quality.sample_times(self.shots, self.plan)
        frames = {round(value * 30) for value in samples}
        self.assertTrue({0, 36, 72, 489, 504, 510, 511, 512, 513, 525, 540, 4777} <= frames)
        for current in self.shots:
            self.assertTrue(set(quality.shot_times(current, self.plan)) <= set(samples))
        self.assertTrue(all(0 <= value < self.plan['duration'] for value in samples))


class AudioEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='vibe-audio-audit-')
        self.folder = Path(self.temporary.name)
        self.assertEqual(Path(tempfile.gettempdir()).resolve(), self.folder.resolve().parent)
        self.addCleanup(self.temporary.cleanup)
        self.plan = {'duration': 8}
        self.config = {'music': 'music.wav', 'music_gain_db': -18, 'narration': 'narration.json'}
        self.data = {'backend': 'edge', 'voice': 'zh-CN-YunjianNeural', 'rate': '+0%',
                     'music_mode': 'constant', 'protected_gaps': [],
                     'cues': [{'id': 'p1', 'start': .2, 'end': 2, 'text': 'First complete paragraph.'},
                              {'id': 'p2', 'start': 4, 'end': 6, 'text': 'Second complete paragraph.'}]}
        self.out = self.folder / 'build'
        self.out.mkdir()
        wave_file(self.folder / 'music.wav', 8)
        wave_file(self.out / 'soundtrack.wav', 8)
        self.timing = {'music_mode': 'constant', 'cues': []}
        for cue in self.data['cues']:
            cache = self.folder / 'audio/narration' / cue['id']
            wave_file(cache / 'source.wav', 1)
            digest = quality.sha256(cache / 'source.wav')
            write_json(cache / 'source.json', {'signature': cue_signature(self.data, cue), 'sha256': digest})
            self.timing['cues'].append({**cue, 'actual_end': cue['start'] + 1, 'tempo': 1, 'sha256': digest})
        self.report = {'music_sha256': quality.sha256(self.folder / 'music.wav'), 'music_gain_db': -18,
                       'events': [], 'narration': {'music_mode': 'constant',
                                                 'music_envelope_min': 1, 'music_envelope_max': 1}}
        self.save_reports()

    def save_reports(self):
        write_json(self.folder / 'narration.json', self.data)
        write_json(self.out / 'narration-timing.json', self.timing)
        write_json(self.out / 'soundtrack.json', self.report)
        write_json(self.out / 'audio-inputs.json', {
            'input_sha256': quality.audio_input_signature(self.folder, self.config, self.plan),
            'soundtrack_sha256': quality.sha256(self.out / 'soundtrack.wav'),
            'mix_report_sha256': quality.sha256(self.out / 'soundtrack.json'),
            'timing_report_sha256': quality.sha256(self.out / 'narration-timing.json')})

    def audit(self):
        return quality.audio_audit(self.folder, self.config, self.plan)

    def test_real_timing_gap_is_advisory_and_no_listening_is_claimed(self):
        result = self.audit()
        self.assertTrue(result['ok'], result)
        self.assertEqual('not_performed', result['subjective_listening'])
        self.assertEqual(2.8, result['paragraph_gaps'][0]['seconds'])
        self.assertEqual('long_paragraph_gap', result['warnings'][0]['type'])

    def test_music_reserve_does_not_get_reported_as_slow_paragraph_pacing(self):
        self.data['protected_gaps'] = [[2, 4]]
        self.save_reports()
        result = self.audit()
        self.assertTrue(result['ok'], result)
        self.assertEqual([], result['warnings'])

    def test_measured_overrun_and_time_stretch_are_rejected(self):
        for changes, message in [({'actual_end': 2.2}, 'window'), ({'tempo': 1.03}, 'time-stretched')]:
            original = self.timing['cues'][0].copy()
            self.timing['cues'][0].update(changes)
            self.save_reports()
            self.assertTrue(any(message in error for error in self.audit()['errors']))
            self.timing['cues'][0] = original

    def test_actual_ducking_cannot_be_hidden_by_constant_script_setting(self):
        self.report['narration']['music_envelope_min'] = .3
        self.save_reports()
        self.assertTrue(any('constant music envelope' in error for error in self.audit()['errors']))

    def test_stale_soundtrack_and_changed_inputs_invalidate_evidence(self):
        wave_file(self.out / 'soundtrack.wav', 7.8)
        self.assertFalse(self.audit()['ok'])
        self.save_reports()
        wave_file(self.folder / 'audio/narration/p1/source.wav', 1.2)
        errors = self.audit()['errors']
        self.assertTrue(any('receipt is stale' in error for error in errors))
        self.assertTrue(any('voice cache' in error for error in errors))


class AnimaticIntegrationTests(unittest.TestCase):
    def test_full_animatic_preserves_production_gate_and_has_real_audio(self):
        if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
            self.skipTest('FFmpeg and FFprobe are required for the real media smoke test')
        with tempfile.TemporaryDirectory(prefix='vibe-animatic-') as temporary:
            self.assertEqual(Path(tempfile.gettempdir()).resolve(), Path(temporary).resolve().parent)
            root = Path(temporary) / '移动 工作区'
            folder = root / 'videos' / 'smoke'
            folder.mkdir(parents=True)
            fonts = root / 'assets/fonts'
            fonts.mkdir(parents=True)
            for filename in ('Lora.ttf', 'Lora-Italic.ttf', 'NotoSerifSC-VF.ttf'):
                shutil.copy2(quality.ROOT / 'assets/fonts' / filename, fonts / filename)
            duration = 2.25
            plan = {'duration': duration, 'fps': 30, 'frames': math.ceil(duration * 30),
                    'impact_frame': 30}
            config = {'entry': 'index.html', 'sources': ['index.html'], 'music': 'music.wav',
                      'music_gain_db': -18, 'ambience_gain': 0, 'production_ready': False}
            write_json(folder / 'film.json', config)
            write_json(folder / 'plan.json', plan)
            shots = [shot(f'view{index + 1}', index * duration / 10, (index + 1) * duration / 10)
                     for index in range(10)]
            write_json(folder / 'shots.json', shots)
            wave_file(folder / 'music.wav', duration)
            (folder / 'index.html').write_text('''<!doctype html><canvas id="stage" width="1920" height="1080"></canvas>
                <script>const ctx=document.getElementById('stage').getContext('2d');
                window.render=t=>{ctx.fillStyle='#07121c';ctx.fillRect(0,0,1920,1080);
                ctx.fillStyle='#e6bd66';ctx.fillRect(200+t*300,300,200,200)};
                window.audit=t=>[];window.READY=true;</script>''', encoding='utf-8')
            before = (folder / 'film.json').read_bytes()
            renderer_root = quality.render.ROOT
            with patch.object(quality, 'ROOT', root), patch.object(quality, 'load', return_value=(folder, config, plan)):
                manifest = quality.build_animatic('smoke', jobs=1)
                self.assertTrue(quality.audio_audit(folder, config, plan)['ok'])
                with self.assertRaisesRegex(ValueError, 'Creative review'):
                    quality.finalize('smoke')
                self.assertFalse((folder / 'build/final_video.mp4').exists())
                # Reuse the tiny real encoded fixture to exercise extraction, without another render.
                final = folder / 'build/final_video.mp4'
                shutil.copy2(folder / manifest['animatic'], final)
                (folder / 'build/review').mkdir(exist_ok=True)
                write_json(folder / 'build/review/validation.json', {
                    'all_technical_checks_pass': True, 'sha256': quality.sha256(final)})
                write_json(folder / 'build/picture.render.json', {'source_sha256': manifest['source_sha256']})
                write_json(folder / 'build/review/layout_audit.json', {'source_sha256': manifest['source_sha256']})
                encoded = quality.final_evidence(folder, config, plan, shots)
                self.assertEqual(quality.sha256(final), encoded['final_video_sha256'])
                self.assertEqual(2, len(encoded['contact_sheets']))
                self.assertEqual(math.ceil(len(encoded['images']) / 12), len(encoded['overview_sheets']))
                self.assertEqual([round(t * 30) for t in quality.sample_times(shots, plan)],
                                 [entry['frame'] for entry in encoded['images']])
                for entry in encoded['images']:
                    # The golden rectangle moves exactly 10 pixels per frame: catch select/name offsets.
                    pixels = np.asarray(quality.Image.open(folder / entry['file']).convert('RGB'))[400]
                    left = np.flatnonzero((pixels[:, 0] > 150) & (pixels[:, 1] > 120))[0]
                    self.assertLessEqual(abs(left - (200 + entry['frame'] * 10)), 3)
                self.assertEqual('not_performed', encoded['continuous_visual_review'])
                self.assertEqual('not_performed', encoded['subjective_listening'])
                for path in encoded['overview_sheets']:
                    with quality.Image.open(folder / path) as overview:
                        self.assertLessEqual(overview.height, 4 * 390)
                final.write_bytes(b'replaced final file invalidates extracted evidence')
                with self.assertRaisesRegex(ValueError, 'current successful encoded-video validation'):
                    quality.final_evidence(folder, config, plan, shots)
            self.assertEqual(before, (folder / 'film.json').read_bytes())
            self.assertEqual(renderer_root, quality.render.ROOT)
            self.assertTrue(manifest['all_media_checks_pass'])
            self.assertEqual(68, manifest['frames'])
            self.assertEqual('not_assessed', manifest['creative_approval'])
            self.assertEqual(3, len(manifest['shots'][0]['action_frames']))
            paths = ([manifest['animatic'], manifest['soundtrack']] + manifest['contact_sheets']
                     + manifest['overview_sheets'] + [entry['file'] for entry in manifest['images']])
            self.assertTrue(all((folder / path).is_file() for path in paths))
            self.assertTrue(all(not Path(path).is_absolute() for path in paths))


class FinalAudioGateTests(unittest.TestCase):
    def test_final_pipeline_preserves_audio_receipt_and_stops_on_failed_audit(self):
        with tempfile.TemporaryDirectory(prefix='vibe-final-audio-') as temporary:
            folder = Path(temporary)
            self.assertEqual(Path(tempfile.gettempdir()).resolve(), folder.resolve().parent)
            review = folder / 'build/review'
            review.mkdir(parents=True)
            write_json(review / 'validation.json', {'all_technical_checks_pass': True})
            config = {'production_ready': True}
            with patch.object(quality, 'load', return_value=(folder, config, {})), \
                    patch.object(quality, 'read_shots', return_value=([], {'ok': True})), \
                    patch.object(quality, 'mix_with_receipt') as mixer, \
                    patch.object(quality, 'audio_audit', return_value={'ok': True, 'errors': []}) as audit, \
                    patch.object(quality, 'final_evidence') as capture, \
                    patch.object(quality.subprocess, 'run') as command:
                checked = quality.finalize('test-episode')
                self.assertTrue(checked['all_technical_checks_pass'])
                mixer.assert_called_once()
                capture.assert_called_once()
                self.assertEqual(['preview', 'render', 'finalize'],
                                 [call.args[0][2] for call in command.call_args_list])
                self.assertTrue((review / 'audio-audit.json').is_file())
                command.reset_mock()
                audit.return_value = {'ok': False, 'errors': ['Voice exceeds the protected window']}
                with self.assertRaisesRegex(ValueError, 'Final audio audit'):
                    quality.finalize('test-episode')
                command.assert_not_called()


if __name__ == '__main__':
    unittest.main()
