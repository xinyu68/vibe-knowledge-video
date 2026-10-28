"""Behavioral checks for local orchestration without TTS or browser rendering."""

import copy
import http.client
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer

from tools.n8n_bridge import Bridge, BridgeError, Handler, read_json, service_lock, write_json


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='video-bridge-')
        self.root = Path(self.temporary.name).resolve()
        self.source = self.root / 'videos/source-film'
        self.source.mkdir(parents=True)
        (self.root / 'assets/music').mkdir(parents=True)
        (self.root / 'assets/fonts').mkdir(parents=True)
        (self.root / 'assets/music/music.mp3').write_bytes(b'music')
        (self.root / 'assets/fonts/font.ttf').write_bytes(b'font')
        (self.root / 'vibe.py').write_text('# fake test entry point\n', encoding='utf-8')
        (self.root / 'tts.py').write_text('# fake test TTS\n', encoding='utf-8')
        self.config = {'title': '测试影片', 'entry': 'index.html', 'plan': 'plan.json', 'output': 'build',
                       'music': '../../assets/music/music.mp3', 'narration': 'narration.json',
                       'sources': ['index.html', 'plan.json', 'plan.js', 'scenes.js'], 'production_ready': True}
        self.plan = {'fps': 30, 'duration': 30, 'frames': 900, 'title': '测试影片',
                     'subtitles': [{'start': 0, 'end': 3, 'zh': '第一句', 'en': 'First line'}]}
        write_json(self.source / 'film.json', self.config)
        write_json(self.source / 'plan.json', self.plan)
        write_json(self.source / 'narration.json', {'cues': [{'id': 'p01', 'start': 0, 'end': 5, 'text': '一段完整的叙述。'}]})
        for name in ['index.html', 'player.html', 'plan.js', 'scenes.js']:
            (self.source / name).write_text('fixture source', encoding='utf-8')
        for name in ['build', 'build-old', 'buildcustom', 'review', 'reference', '.git']:
            (self.source / name).mkdir()
            (self.source / name / 'do-not-copy.txt').write_text('original output', encoding='utf-8')
        (self.source / 'audio/narration/p01').mkdir(parents=True)
        (self.source / 'audio/narration/p01/source.wav').write_bytes(b'cached-wave')
        (self.source / '.env').write_text('SECRET=never-serve', encoding='utf-8')
        self.bridge = Bridge(self.root, start_worker=False)
        self.commands = []

    def tearDown(self):
        self.bridge.close()
        self.temporary.cleanup()

    def create(self, request_id='create-1'):
        return self.bridge.create_run({'source_slug': 'source-film', 'preview_start': 0, 'preview_end': 12, 'request_id': request_id})

    def fake_popen(self, arguments, **kwargs):
        self.commands.append(arguments)
        if Path(arguments[1]).name == 'vibe.py':
            stage, slug = arguments[2:4]
            output = self.root / 'videos' / slug / 'build'
            output.mkdir(exist_ok=True)
            if stage == 'narrate':
                (output / 'narration.wav').write_bytes(b'narration')
            elif stage == 'mix':
                (output / 'soundtrack.wav').write_bytes(b'mix')
            elif stage == 'preview':
                write_json(output / 'review/layout_audit.json', {'layout_issue_frames': 0})
            elif stage == 'render':
                name = arguments[arguments.index('--name') + 1] if '--name' in arguments else 'picture'
                (output / (name + '.mp4')).write_bytes(b'picture')
                write_json(output / (name + '.render.json'), {'frames': 900})
            elif stage == 'finalize':
                (output / 'final_video.mp4').write_bytes(b'final')
        elif arguments[0] == 'ffmpeg':
            Path(arguments[-1]).write_bytes(b'media output')
        return FakeProcess()

    def execute_stage(self, run_id, stage, request_id=None):
        job = self.bridge.submit(run_id, {'stage': stage, 'request_id': request_id or stage + '-1'})
        with patch('tools.n8n_bridge.subprocess.Popen', side_effect=self.fake_popen), patch.dict(os.environ, {'VIBE_TTS_CLI': str(self.root / 'tts.py')}):
            self.bridge._execute(job['job_id'])
        result = self.bridge.job_snapshot(job['job_id'])
        self.assertEqual('succeeded', result['status'], result)
        return result

    def assert_error(self, code, callable_, *args):
        with self.assertRaises(BridgeError) as caught:
            callable_(*args)
        self.assertEqual(code, caught.exception.code)

    def test_snapshot_is_independent_and_keeps_portable_music_and_audio_cache(self):
        before = {p.relative_to(self.source).as_posix(): p.read_bytes() for p in self.source.rglob('*') if p.is_file()}
        run = self.create()
        target = self.root / 'videos' / run['slug']
        self.assertFalse(read_json(target / 'film.json')['production_ready'])
        self.assertEqual('../../assets/music/music.mp3', read_json(target / 'film.json')['music'])
        self.assertEqual(b'cached-wave', (target / 'audio/narration/p01/source.wav').read_bytes())
        self.assertFalse(any(p.name.startswith('build') for p in target.iterdir()))
        self.assertFalse((target / '.env').exists())
        (target / 'scenes.js').write_text('new animation', encoding='utf-8')
        after = {p.relative_to(self.source).as_posix(): p.read_bytes() for p in self.source.rglob('*') if p.is_file()}
        self.assertEqual(before, after)

    def test_snapshot_normalizes_explicit_local_music_to_a_relative_reference(self):
        config = copy.deepcopy(self.config)
        config['music'] = str(self.root / 'assets/music/music.mp3')
        write_json(self.source / 'film.json', config)
        run = self.create()
        self.assertEqual('../../assets/music/music.mp3', read_json(self.root / 'videos' / run['slug'] / 'film.json')['music'])

    def test_create_and_job_retries_are_persistent_and_do_not_duplicate_work(self):
        run = self.create()
        self.assertEqual(run['run_id'], self.create()['run_id'])
        self.assert_error('idempotency_conflict', self.bridge.create_run,
                          {'source_slug': 'source-film', 'preview_end': 10, 'request_id': 'create-1'})
        job = self.bridge.submit(run['run_id'], {'stage': 'narrate', 'request_id': 'n1'})
        same = self.bridge.submit(run['run_id'], {'stage': 'narrate', 'request_id': 'retry1'})
        self.assertEqual(job['job_id'], same['job_id'])
        restarted = Bridge(self.root, start_worker=False, recover_interrupted=True)
        try:
            self.assertEqual(run['run_id'], restarted.create_run({'source_slug': 'source-film', 'preview_start': 0, 'preview_end': 12, 'request_id': 'create-1'})['run_id'])
            interrupted = restarted.job_snapshot(job['job_id'])
            self.assertEqual('failed', interrupted['status'])
            self.assertTrue(interrupted['interrupted'])
            self.assertIsNone(interrupted['result'])
        finally:
            restarted.close()

    def test_project_service_lock_and_non_recovering_read_do_not_interrupt_jobs(self):
        run = self.create()
        job = self.bridge.submit(run['run_id'], {'stage': 'narrate', 'request_id': 'live'})
        handle = service_lock(self.root)
        try:
            with self.assertRaises(RuntimeError):
                service_lock(self.root)
            reader = Bridge(self.root, start_worker=False)
            self.assertEqual('queued', reader.job_snapshot(job['job_id'])['status'])
            self.assertEqual('queued', read_json(self.bridge.jobs_dir / (job['job_id'] + '.json'))['status'])
        finally:
            handle.close()
        acquired_again = service_lock(self.root)
        acquired_again.close()

    def test_render_requires_current_preview_then_explicit_approval(self):
        run_id = self.create()['run_id']
        self.assert_error('approval_required', self.bridge.submit, run_id, {'stage': 'render', 'request_id': 'r1'})
        self.assert_error('preview_required', self.bridge.review, run_id, {'decision': 'approve', 'expected_revision': 1})
        self.assert_error('narration_required', self.bridge.submit, run_id, {'stage': 'preview', 'request_id': 'p1'})
        self.execute_stage(run_id, 'narrate')
        self.execute_stage(run_id, 'preview')
        approved = self.bridge.review(run_id, {'decision': 'approve', 'expected_revision': 1, 'feedback': '看过预览，确认继续'})
        self.assertTrue(approved['production_ready'])
        self.execute_stage(run_id, 'render')
        render_commands = [c[2] for c in self.commands if len(c) > 2 and Path(c[1]).name == 'vibe.py']
        self.assertEqual(['preview', 'render'], render_commands[-2:])
        final = self.execute_stage(run_id, 'finalize')
        self.assertEqual('completed', final['result']['status'])
        self.assertIsNotNone(final['result']['artifacts']['final_video'])
        self.assertTrue(read_json(self.source / 'film.json')['production_ready'])

    def test_edits_create_revision_preserve_previous_and_invalidate_stages(self):
        run = self.create()
        self.execute_stage(run['run_id'], 'narrate')
        self.execute_stage(run['run_id'], 'preview')
        old_folder = self.root / 'videos' / run['slug']
        before = (old_folder / 'narration.json').read_bytes()
        edit = {'decision': 'revise', 'expected_revision': 1, 'feedback': '缩短第一段', 'cue_id': 'p01', 'text': '更简短。',
                'subtitles': [{'index': 0, 'zh': '新字幕', 'en': 'New subtitle'}], 'request_id': 'revision-one'}
        revised = self.bridge.review(run['run_id'], edit)
        self.assertEqual(2, revised['revision'])
        self.assertFalse(revised['production_ready'])
        self.assertEqual('更简短。', revised['cues'][0]['text'])
        self.assertEqual('新字幕', revised['subtitles'][0]['zh'])
        self.assertEqual(0, revised['subtitles'][0]['start'])
        self.assertTrue(all(value is None for value in revised['stages'].values()))
        self.assertIsNone(revised['artifacts']['preview'])
        self.assertEqual(before, (old_folder / 'narration.json').read_bytes())
        self.assertTrue((old_folder / 'build/preview.mp4').is_file())
        self.assertEqual(2, self.bridge.review(run['run_id'], edit)['revision'])
        self.assert_error('stale_revision', self.bridge.review, run['run_id'], {'decision': 'approve', 'expected_revision': 1})
        self.assert_error('approval_required', self.bridge.submit, run['run_id'], {'stage': 'render', 'request_id': 'rev-render'})
        third = self.bridge.review(run['run_id'], {'decision': 'revise', 'expected_revision': 2, 'feedback': '动画另行人工修改'})
        self.assertEqual('更简短。', third['cues'][0]['text'])
        self.assertFalse(third['feedback'][-1]['explicit_text_edits'])
        self.assert_error('revision_limit', self.bridge.review, run['run_id'], {'decision': 'revise', 'expected_revision': 3})

    def test_source_change_after_preview_is_not_approvable(self):
        run = self.create()
        self.execute_stage(run['run_id'], 'narrate')
        self.execute_stage(run['run_id'], 'preview')
        (self.root / 'videos' / run['slug'] / 'scenes.js').write_text('changed after preview', encoding='utf-8')
        self.assert_error('preview_required', self.bridge.review, run['run_id'], {'decision': 'approve', 'expected_revision': 1})

    def test_shared_music_change_invalidates_review_and_old_media_links(self):
        run = self.create()
        self.execute_stage(run['run_id'], 'narrate')
        self.execute_stage(run['run_id'], 'preview')
        self.bridge.review(run['run_id'], {'decision': 'approve', 'expected_revision': 1})
        (self.root / 'assets/music/music.mp3').write_bytes(b'different soundtrack at same path')
        state = self.bridge.snapshot(run['run_id'])
        self.assertEqual('stale', state['review_status'])
        self.assertFalse(state['production_ready'])
        self.assertIsNone(state['artifacts']['preview'])
        self.assertIsNone(state['artifacts']['soundtrack'])
        self.assert_error('approval_required', self.bridge.submit, run['run_id'], {'stage': 'render', 'request_id': 'changed-audio-render'})

    def test_old_final_file_is_not_presented_as_current_after_edit(self):
        run = self.create()
        self.execute_stage(run['run_id'], 'narrate')
        self.execute_stage(run['run_id'], 'preview')
        self.bridge.review(run['run_id'], {'decision': 'approve', 'expected_revision': 1})
        self.execute_stage(run['run_id'], 'render')
        self.execute_stage(run['run_id'], 'finalize')
        folder = self.root / 'videos' / run['slug']
        self.assertTrue((folder / 'build/final_video.mp4').exists())
        (folder / 'scenes.js').write_text('new scene', encoding='utf-8')
        self.bridge.submit(run['run_id'], {'stage': 'narrate', 'request_id': 'changed-source-narrate'})
        self.assertIsNone(self.bridge.snapshot(run['run_id'])['artifacts']['final_video'])

    def test_failure_is_durable_and_cancellation_does_not_start_queued_job(self):
        run_id = self.create()['run_id']
        first = self.bridge.submit(run_id, {'stage': 'narrate', 'request_id': 'fail-one'})
        with patch('tools.n8n_bridge.subprocess.Popen', return_value=FakeProcess(7)), patch.dict(os.environ, {'VIBE_TTS_CLI': str(self.root / 'tts.py')}):
            self.bridge._execute(first['job_id'])
        failure = self.bridge.job_snapshot(first['job_id'])
        self.assertEqual('failed', failure['status'])
        self.assertIn('exit code 7', failure['error'])
        self.assertIn('narrate', failure['log_tail'])
        self.assertEqual('failed', read_json(self.bridge.jobs_dir / (first['job_id'] + '.json'))['status'])
        retry = self.bridge.submit(run_id, {'stage': 'narrate', 'request_id': 'retry-two'})
        self.bridge.cancel(retry['job_id'])
        with patch('tools.n8n_bridge.subprocess.Popen') as popen:
            self.bridge._execute(retry['job_id'])
            popen.assert_not_called()
        self.assertEqual('cancelled', self.bridge.job_snapshot(retry['job_id'])['status'])
        self.assertEqual('cancelled', self.bridge.snapshot(run_id)['status'])
        slug = self.bridge.snapshot(run_id)['slug']
        (self.root / 'videos' / slug / 'scenes.js').write_text('edit while stopped', encoding='utf-8')
        self.assertEqual('cancelled', self.bridge.snapshot(run_id)['status'])
        # Stopping a stage is recoverable; only an explicit run-level cancel
        # decision permanently prevents more work on that run.
        resumed = self.bridge.submit(run_id, {'stage': 'narrate', 'request_id': 'explicit-retry-after-stop'})
        self.assertNotEqual(retry['job_id'], resumed['job_id'])
        self.assertEqual('queued', self.bridge.snapshot(run_id)['status'])

    def test_cancelled_render_is_visible_in_run_status_and_can_be_retried(self):
        run_id = self.create()['run_id']
        self.execute_stage(run_id, 'narrate')
        self.execute_stage(run_id, 'preview')
        self.bridge.review(run_id, {'decision': 'approve', 'expected_revision': 1})
        rendering = self.bridge.submit(run_id, {'stage': 'render', 'request_id': 'render-stopped'})
        self.bridge.cancel(rendering['job_id'])
        state = self.bridge.snapshot(run_id)
        self.assertEqual('cancelled', state['status'])
        self.assertEqual('approved', state['review_status'])
        self.assertIsNotNone(state['artifacts']['preview'])
        self.assertIsNone(state['artifacts']['final_video'])
        retry = self.bridge.submit(run_id, {'stage': 'render', 'request_id': 'render-resumed'})
        self.assertEqual('queued', retry['status'])
        self.assertEqual('queued', self.bridge.snapshot(run_id)['status'])

    def test_cancel_running_job_targets_only_its_process_tree(self):
        run_id = self.create()['run_id']
        first = self.bridge.submit(run_id, {'stage': 'narrate', 'request_id': 'running-one'})
        job = self.bridge.jobs[first['job_id']]
        job['status'] = 'running'
        process = FakeProcess()
        self.bridge.processes[first['job_id']] = process
        with patch.object(self.bridge, '_terminate') as terminate:
            self.bridge.cancel(first['job_id'])
            terminate.assert_called_once_with(process)
        self.assertTrue(job['cancel_requested'])
        job['status'] = 'cancelled'
        self.bridge.processes.clear()

    def test_tree_termination_is_scoped_to_the_tracked_process_id(self):
        process = FakeProcess()
        if os.name == 'nt':
            with patch('tools.n8n_bridge.subprocess.run', return_value=subprocess.CompletedProcess([], 0)) as run:
                Bridge._terminate(process)
                self.assertEqual(['taskkill', '/PID', '12345', '/T', '/F'], run.call_args.args[0])
                self.assertNotIn('shell', run.call_args.kwargs)
        else:
            with patch('tools.n8n_bridge.os.killpg') as kill:
                Bridge._terminate(process)
                self.assertEqual(12345, kill.call_args.args[0])

    def test_path_rejection_for_source_resources_and_media(self):
        self.assert_error('invalid_id', self.bridge.create_run, {'source_slug': '../source-film', 'request_id': 'escape'})
        run = self.create()
        for path in ['/project/videos/source-film/index.html', '/project/tools/n8n_bridge.py',
                     '/project/videos/' + run['slug'] + '/.env', '/project/assets/music/../../vibe.py']:
            with self.assertRaises(BridgeError):
                self.bridge.media(path)
        valid = '/project/videos/' + run['slug'] + '/player.html'
        self.assertEqual('player.html', self.bridge.media(valid).name)
        self.assertEqual('music.mp3', self.bridge.media('/project/assets/music/music.mp3').name)
        broken = copy.deepcopy(self.config)
        broken['plan'] = '../../outside.json'
        write_json(self.source / 'film.json', broken)
        self.assert_error('unsafe_path', self.bridge.create_run, {'source_slug': 'source-film', 'request_id': 'unsafe-config'})

    def test_http_origin_guard_body_limit_and_media_range(self):
        run = self.create()
        media = self.root / 'videos' / run['slug'] / 'sample.mp4'
        media.write_bytes(b'0123456789')
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        server.bridge = self.bridge
        self.bridge.port = server.server_port
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()

        def request(method, path, body=None, headers=None):
            connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            result = response.status, dict(response.headers), response.read()
            connection.close()
            return result

        try:
            self.assertEqual(200, request('GET', '/health')[0])
            self.assertEqual(403, request('GET', '/health', headers={'Host': 'attacker.test'})[0])
            self.assertEqual(403, request('GET', '/health', headers={'Origin': 'https://attacker.test'})[0])
            self.assertEqual(200, request('GET', '/health', headers={'Origin': 'http://127.0.0.1:5678'})[0])
            self.assertEqual(415, request('POST', '/api/runs', body='{}', headers={'Content-Type': 'text/plain'})[0])
            self.assertEqual(413, request('POST', '/api/runs', body='x' * 131073, headers={'Content-Type': 'application/json'})[0])
            url = '/project/videos/' + run['slug'] + '/sample.mp4'
            status, headers, body = request('GET', url, headers={'Range': 'bytes=2-5'})
            self.assertEqual((206, b'2345', 'bytes 2-5/10'), (status, body, headers['Content-Range']))
            self.assertEqual(b'789', request('GET', url, headers={'Range': 'bytes=-3'})[2])
            self.assertEqual(416, request('GET', url, headers={'Range': 'bytes=20-'})[0])
            self.assertEqual(400, request('GET', '/project/assets/music/%2e%2e/%2e%2e/vibe.py')[0])
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=3)


class FakeProcess:
    pid = 12345

    def __init__(self, returncode=0):
        self.returncode = returncode

    def wait(self, timeout=None):
        return self.returncode

    def poll(self):
        return None


if __name__ == '__main__':
    unittest.main()
