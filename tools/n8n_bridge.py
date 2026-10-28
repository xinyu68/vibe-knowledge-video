"""Loopback-only, persistent n8n adapter for the existing video CLI.

This service orchestrates prepared episodes. It does not write stories or claim
that free-form review feedback has been implemented in animation code.
"""

import argparse
import copy
import hashlib
import json
import math
import mimetypes
import os
from pathlib import Path
import queue
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import quote, unquote, urlsplit
import uuid


STAGES = ('narrate', 'preview', 'render', 'finalize')
ACTIVE = {'queued', 'running'}
ID = re.compile(r'^[a-f0-9]{16}$')
SLUG = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
MEDIA_TYPES = {'.html', '.js', '.css', '.json', '.png', '.jpg', '.jpeg', '.webp',
               '.gif', '.svg', '.ttf', '.woff', '.woff2', '.mp4', '.wav', '.mp3', '.srt', '.vtt'}
MAX_BODY = 128 * 1024


class BridgeError(Exception):
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status, self.code = status, code


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def now():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def inside(base, value):
    base = Path(base).resolve()
    target = (base / value).resolve()
    if not target.is_relative_to(base):
        raise BridgeError(400, 'unsafe_path', 'Path must stay inside its allowed directory')
    return target


def identifier(value, expression=ID):
    if not isinstance(value, str) or not expression.fullmatch(value):
        raise BridgeError(400, 'invalid_id', 'Invalid identifier')
    return value


def service_lock(root):
    """Hold one process-wide service lock per project, even on different ports."""
    path = Path(root) / '.local/n8n/service.lock'
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = path.open('a+b')
    if stream.tell() == 0:
        stream.write(b'0')
        stream.flush()
    stream.seek(0)
    try:
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        stream.close()
        raise RuntimeError('Another bridge service already owns this project')
    return stream


class Bridge:
    def __init__(self, root=None, port=5681, start_worker=True, max_revisions=2, recover_interrupted=False):
        self.root = Path(root or Path(__file__).resolve().parents[1]).resolve()
        self.port, self.max_revisions = port, max_revisions
        self.state = self.root / '.local/n8n'
        self.runs_dir, self.jobs_dir = self.state / 'runs', self.state / 'jobs'
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.tasks, self.processes = queue.Queue(), {}
        self.stopping = threading.Event()
        self.requests_path = self.state / 'requests.json'
        self.requests = read_json(self.requests_path) if self.requests_path.exists() else {}
        self.runs = {p.parent.name: read_json(p) for p in self.runs_dir.glob('*/run.json')}
        self.jobs = {p.stem: read_json(p) for p in self.jobs_dir.glob('*.json')}
        # A terminated service cannot certify the outcome of a child process.
        # Do not rerun a partially completed render invisibly on restart.
        if recover_interrupted:
            for job in self.jobs.values():
                if job['status'] in ACTIVE:
                    job.update(status='failed', error='Service restarted: previous task was interrupted; retry explicitly.',
                               finished_at=now(), interrupted=True)
                    self._save_job(job)
        self.worker = None
        if start_worker:
            self.worker = threading.Thread(target=self._work, daemon=True, name='video-worker')
            self.worker.start()

    def _save_run(self, run):
        write_json(self.runs_dir / run['run_id'] / 'run.json', run)

    def _save_job(self, job):
        write_json(self.jobs_dir / (job['job_id'] + '.json'), job)

    def _run(self, run_id):
        identifier(run_id)
        if run_id not in self.runs:
            raise BridgeError(404, 'not_found', 'Run not found')
        return self.runs[run_id]

    def _job(self, job_id):
        identifier(job_id)
        if job_id not in self.jobs:
            raise BridgeError(404, 'not_found', 'Job not found')
        return self.jobs[job_id]

    def _current(self, run):
        return run['revisions'][-1]

    def _episode(self, slug):
        identifier(slug, SLUG)
        folder = inside(self.root / 'videos', slug)
        if not (folder / 'film.json').is_file():
            raise BridgeError(404, 'not_found', 'Episode not found')
        config = read_json(folder / 'film.json')
        plan_path = inside(folder, config.get('plan', 'plan.json'))
        plan = read_json(plan_path)
        for field in ('entry', 'plan', 'narration'):
            if config.get(field) and not inside(folder, config[field]).is_file():
                raise BridgeError(400, 'invalid_episode', f'Episode {field} is missing')
        for name in config.get('sources', []):
            if not inside(folder, name).is_file():
                raise BridgeError(400, 'invalid_episode', 'Episode source is missing')
        inside(folder, config.get('output', 'build'))
        music = (folder / config.get('music', '')).resolve()
        if not music.is_relative_to((self.root / 'assets/music').resolve()) or not music.is_file():
            raise BridgeError(400, 'invalid_music', 'Music must be an existing file under assets/music')
        duration = plan.get('duration')
        if not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration <= 0:
            raise BridgeError(400, 'invalid_episode', 'Invalid episode duration')
        if plan.get('fps') != 30 or plan.get('frames') != math.ceil(duration * 30 - 1e-8):
            raise BridgeError(400, 'invalid_episode', 'Episode must use a consistent 30 fps timeline')
        return folder, config, plan

    def episodes(self):
        result = []
        for path in sorted((self.root / 'videos').glob('*/film.json')):
            if path.parent.name.startswith('n8n-'):
                continue
            try:
                folder, config, plan = self._episode(path.parent.name)
                if config.get('test_only'):
                    continue
                result.append({'slug': folder.name, 'title': config.get('title', folder.name),
                               'duration': plan['duration'], 'has_narration': bool(config.get('narration')),
                               'production_ready': bool(config.get('production_ready'))})
            except (BridgeError, ValueError, OSError, KeyError):
                continue
        return {'episodes': result}

    def _request(self, scope, data, required=True):
        request_id = data.get('request_id')
        if not request_id and not required:
            return None, None
        if not isinstance(request_id, str) or not re.fullmatch(r'[\w.:\-]{1,128}', request_id, re.ASCII):
            raise BridgeError(400, 'request_id_required', 'Supply a request_id of 1–128 letters, digits, _, ., : or -')
        key = scope + ':' + request_id
        signature = digest(data)
        previous = self.requests.get(key)
        if previous and previous['signature'] != signature:
            raise BridgeError(409, 'idempotency_conflict', 'This request_id was already used with different input')
        return key, previous

    def _remember(self, key, data, result):
        if key:
            self.requests[key] = {'signature': digest(data), 'result': result}
            write_json(self.requests_path, self.requests)

    def _clone(self, source, slug):
        target = inside(self.root / 'videos', slug)
        if target.exists():
            raise BridgeError(409, 'snapshot_exists', 'Snapshot directory already exists')

        def ignored(directory, names):
            omitted = []
            for name in names:
                path = Path(directory) / name
                if name.startswith('.') or name.lower().startswith('build') or name in {'reference', 'review', '__pycache__', 'node_modules'}:
                    omitted.append(name)
                elif path.is_symlink() or not path.resolve().is_relative_to(source.resolve()):
                    raise BridgeError(400, 'unsafe_path', 'Linked source resources are not allowed in snapshots')
            return omitted

        try:
            shutil.copytree(source, target, ignore=ignored)
            config = read_json(target / 'film.json')
            config['production_ready'] = False
            config['output'] = 'build'
            music = (source / config['music']).resolve()
            config['music'] = Path(os.path.relpath(music, target)).as_posix()
            write_json(target / 'film.json', config)
            if not (target / 'player.html').exists():
                shutil.copy2(self.root / 'templates/episode/player.html', target / 'player.html')
        except Exception:
            # Only a just-created, verified child of videos may be removed here.
            if target.exists() and target.parent == (self.root / 'videos').resolve() and target.name.startswith('n8n-'):
                shutil.rmtree(target)
            raise
        return target

    def _revision(self, number, slug):
        return {'revision': number, 'slug': slug, 'created_at': now(), 'review_status': 'pending',
                'stages': {}, 'feedback': [], 'approved_input_hash': None, 'preview_input_hash': None}

    def create_run(self, data):
        with self.lock:
            key, previous = self._request('create', data)
            if previous:
                return self.snapshot(previous['result'])
            slug = identifier(data.get('source_slug'), SLUG)
            if slug.startswith('n8n-'):
                raise BridgeError(400, 'invalid_source', 'Select an original episode, not a run snapshot')
            folder, config, plan = self._episode(slug)
            start, end = data.get('preview_start', 0), data.get('preview_end', 12)
            if (not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in (start, end))
                    or not 0 <= start < end <= plan['duration'] or end - start > 60):
                raise BridgeError(400, 'invalid_preview', 'Preview must be a valid interval of at most 60 seconds')
            start_frame, end_frame = round(start * 30), round(end * 30)
            if end_frame <= start_frame or (start_frame == 0 and end_frame >= plan['frames']):
                raise BridgeError(400, 'invalid_preview', 'Preview must be shorter than the complete film')
            run_id = uuid.uuid4().hex[:16]
            target_slug = f'n8n-{run_id}-r01'
            self._clone(folder, target_slug)
            run = {'run_id': run_id, 'source_slug': slug, 'created_at': now(), 'cancelled': False,
                   'preview_start': start_frame / 30, 'preview_end': end_frame / 30,
                   'max_revisions': self.max_revisions, 'revisions': [self._revision(1, target_slug)]}
            self.runs[run_id] = run
            self._save_run(run)
            self._remember(key, data, run_id)
            return self.snapshot(run_id)

    def _input_hash(self, revision):
        folder, config, _ = self._episode(revision['slug'])
        config = copy.deepcopy(config)
        config['production_ready'] = False
        payload = {'film': config}
        names = set(config.get('sources', [])) | {config.get('plan', 'plan.json')}
        if config.get('narration'):
            names.add(config['narration'])
        # plan.js is generated by vibe.py from plan.json, not an independent input.
        names.discard('plan.js')
        for name in sorted(names):
            payload[name] = hashlib.sha256(inside(folder, name).read_bytes()).hexdigest()
        # Shared dependencies affect the reviewed picture/sound as much as the
        # episode sources do. A replacement at the same path needs new review.
        music = (folder / config['music']).resolve()
        payload['music_bytes'] = hashlib.sha256(music.read_bytes()).hexdigest()
        for font in sorted((self.root / 'assets/fonts').rglob('*')):
            if font.is_file():
                if not font.resolve().is_relative_to((self.root / 'assets/fonts').resolve()):
                    raise BridgeError(400, 'unsafe_path', 'Shared fonts must stay inside assets/fonts')
                payload['font:' + font.relative_to(self.root).as_posix()] = hashlib.sha256(font.read_bytes()).hexdigest()
        return digest(payload)

    def _artifact_url(self, folder, path, always=False):
        if always or path.is_file():
            return f'http://127.0.0.1:{self.port}/project/' + quote(path.relative_to(self.root).as_posix())
        return None

    def snapshot(self, run_id):
        with self.lock:
            run = self._run(run_id)
            revision = self._current(run)
            folder, config, plan = self._episode(revision['slug'])
            out = folder / 'build'
            cues = read_json(inside(folder, config['narration'])).get('cues', []) if config.get('narration') else []
            stages = {stage: self.job_summary(revision['stages'][stage]) if stage in revision['stages'] else None for stage in STAGES}
            input_hash = self._input_hash(revision)
            valid = {}
            for stage, summary in stages.items():
                current = bool(summary and self.jobs[summary['job_id']]['input_hash'] == input_hash)
                if summary:
                    summary['current'] = current
                valid[stage] = bool(current and summary['status'] == 'succeeded')
            review_status = revision['review_status']
            if review_status == 'approved' and revision.get('approved_input_hash') != input_hash:
                review_status = 'stale'
            status = 'cancelled' if run['cancelled'] else ('approved' if revision['review_status'] == 'approved' else 'awaiting_review')
            if not run['cancelled']:
                for stage in reversed(STAGES):
                    job = stages[stage]
                    if job and job['status'] in ACTIVE | {'failed', 'cancelled'}:
                        status = job['status']
                        break
                    if job and job['status'] == 'succeeded':
                        if stage == 'finalize':
                            status = 'completed'
                        break
                if not any(stages.values()):
                    status = 'created'
                if (status not in ACTIVE | {'failed', 'cancelled'}
                        and any(summary and not summary['current'] for summary in stages.values())):
                    status = 'needs_preview'
            files = {'player': folder / 'player.html', 'poster': out / 'poster.jpg', 'preview': out / 'preview.mp4',
                     'narration': out / 'narration-preview.mp3', 'soundtrack': out / 'soundtrack.wav',
                     'final_video': out / 'final_video.mp4'}
            available = {'player': True, 'poster': valid['preview'], 'preview': valid['preview'],
                         'narration': valid['narrate'], 'soundtrack': valid['narrate'] or valid['preview'],
                         'final_video': valid['finalize']}
            return {'run_id': run_id, 'source_slug': run['source_slug'], 'revision': revision['revision'],
                    'slug': revision['slug'], 'title': config.get('title', revision['slug']), 'status': status,
                    'review_status': review_status, 'preview_start': run['preview_start'], 'preview_end': run['preview_end'],
                    'duration': plan['duration'], 'production_ready': bool(config.get('production_ready') and review_status == 'approved'),
                    'cues': [{key: cue.get(key) for key in ('id', 'text', 'start', 'end')} for cue in cues],
                    'subtitles': [{'index': i, **cue} for i, cue in enumerate(plan.get('subtitles', []))],
                    'artifacts': {name: self._artifact_url(folder, path, name == 'player') if available[name] else None for name, path in files.items()},
                    'stages': stages, 'feedback': revision['feedback'], 'revision_count': revision['revision'] - 1,
                    'max_revisions': run['max_revisions'],
                    'limitations': 'Free-form feedback is recorded for manual editing. Only explicitly supplied cue/subtitle text is changed; subtitle timing and animation are not automatically rewritten.'}

    def job_summary(self, job_id):
        job = self._job(job_id)
        return {key: job[key] for key in ('job_id', 'run_id', 'revision', 'stage', 'status')} | {
            'status_url': f'http://127.0.0.1:{self.port}/api/jobs/{job_id}'}

    def job_snapshot(self, job_id):
        with self.lock:
            job = self._job(job_id)
            log = self.jobs_dir / (job_id + '.log')
            tail = ''
            if log.exists():
                with log.open('rb') as stream:
                    stream.seek(max(0, log.stat().st_size - 12000))
                    tail = stream.read().decode('utf-8', errors='replace')
            return self.job_summary(job_id) | {key: job.get(key) for key in ('created_at', 'started_at', 'finished_at', 'error', 'result', 'interrupted')} | {'log_tail': tail}

    def _active_for(self, run_id):
        return [job for job in self.jobs.values() if job['run_id'] == run_id and job['status'] in ACTIVE]

    def _stage_succeeded(self, revision, stage):
        job_id = revision['stages'].get(stage)
        return bool(job_id and self.jobs[job_id]['status'] == 'succeeded')

    def submit(self, run_id, data):
        with self.lock:
            run = self._run(run_id)
            key, previous = self._request('job:' + run_id, data)
            if previous:
                return self.job_summary(previous['result'])
            stage = data.get('stage')
            if stage not in STAGES:
                raise BridgeError(400, 'invalid_stage', 'Supported stages: narrate, preview, render, finalize')
            if run['cancelled']:
                raise BridgeError(409, 'cancelled', 'This run has been cancelled')
            revision = self._current(run)
            input_hash = self._input_hash(revision)
            old = self.jobs.get(revision['stages'].get(stage))
            if old and (old['status'] in ACTIVE or (old['status'] == 'succeeded' and old['input_hash'] == input_hash)):
                self._remember(key, data, old['job_id'])
                return self.job_summary(old['job_id'])
            if self._active_for(run_id):
                raise BridgeError(409, 'busy', 'Wait for or cancel the active stage before starting another')
            _, config, _ = self._episode(revision['slug'])
            if stage == 'preview' and config.get('narration') and not self._stage_succeeded(revision, 'narrate'):
                raise BridgeError(409, 'narration_required', 'Run the narration stage before preview')
            if stage in {'render', 'finalize'} and (revision['review_status'] != 'approved' or revision.get('approved_input_hash') != input_hash):
                raise BridgeError(409, 'approval_required', 'Approve the current preview before full rendering')
            if stage == 'finalize' and not self._stage_succeeded(revision, 'render'):
                raise BridgeError(409, 'render_required', 'Complete the full picture render first')
            job_id = uuid.uuid4().hex[:16]
            job = {'job_id': job_id, 'run_id': run_id, 'revision': revision['revision'], 'slug': revision['slug'],
                   'stage': stage, 'status': 'queued', 'created_at': now(), 'error': None, 'result': None,
                   'input_hash': input_hash, 'cancel_requested': False}
            self.jobs[job_id] = job
            revision['stages'][stage] = job_id
            if stage in {'narrate', 'preview'}:
                revision['review_status'] = 'pending'
                revision['approved_input_hash'] = None
                config['production_ready'] = False
                write_json(self.root / 'videos' / revision['slug'] / 'film.json', config)
                for later in STAGES[STAGES.index(stage) + 1:]:
                    revision['stages'].pop(later, None)
            self._save_job(job)
            self._save_run(run)
            self._remember(key, data, job_id)
            self.tasks.put(job_id)
            return self.job_summary(job_id)

    def review(self, run_id, data):
        with self.lock:
            run = self._run(run_id)
            key, previous = self._request('review:' + run_id, data, required=False)
            if previous:
                return self.snapshot(run_id)
            revision = self._current(run)
            if data.get('expected_revision') != revision['revision']:
                raise BridgeError(409, 'stale_revision', 'The run revision changed; reload before reviewing')
            decision = data.get('decision')
            if decision not in {'approve', 'revise', 'cancel'}:
                raise BridgeError(400, 'invalid_decision', 'Decision must be approve, revise or cancel')
            feedback = data.get('feedback', '')
            if not isinstance(feedback, str) or len(feedback) > 12000:
                raise BridgeError(400, 'invalid_feedback', 'Feedback must be text of at most 12000 characters')
            if decision == 'cancel':
                run['cancelled'] = True
                for job in self._active_for(run_id):
                    self.cancel(job['job_id'])
                revision['review_status'] = 'cancelled'
            else:
                if run['cancelled']:
                    raise BridgeError(409, 'cancelled', 'This run has been cancelled')
                if self._active_for(run_id):
                    raise BridgeError(409, 'busy', 'Wait for or cancel the active stage before reviewing')
                folder, config, plan = self._episode(revision['slug'])
                if decision == 'approve':
                    current_hash = self._input_hash(revision)
                    if (not self._stage_succeeded(revision, 'preview') or revision.get('preview_input_hash') != current_hash):
                        raise BridgeError(409, 'preview_required', 'Generate and inspect a preview of the current source before approving')
                    if data.get('cue_id') or data.get('text') is not None or data.get('subtitles'):
                        raise BridgeError(400, 'revise_required', 'Text edits require a revise decision and a new preview')
                    revision.update(review_status='approved', approved_input_hash=current_hash, approved_at=now())
                    config['production_ready'] = True
                    write_json(folder / 'film.json', config)
                elif decision == 'revise':
                    if revision['revision'] - 1 >= run['max_revisions']:
                        raise BridgeError(409, 'revision_limit', 'Revision limit reached; review the project manually before starting a new run')
                    narration = read_json(inside(folder, config['narration'])) if config.get('narration') else None
                    edits = self._validate_edits(data, narration, plan)
                    number = revision['revision'] + 1
                    slug = f'n8n-{run_id}-r{number:02d}'
                    target = self._clone(folder, slug)
                    if edits['cue']:
                        cue_id, text = edits['cue']
                        next(cue for cue in narration['cues'] if cue['id'] == cue_id)['text'] = text
                        write_json(target / config['narration'], narration)
                    if edits['subtitles']:
                        for item in edits['subtitles']:
                            plan['subtitles'][item['index']].update(zh=item['zh'], en=item['en'])
                        write_json(target / config.get('plan', 'plan.json'), plan)
                    revised = self._revision(number, slug)
                    revised['feedback'] = copy.deepcopy(revision['feedback'])
                    run['revisions'].append(revised)
                    revision = revised
            revision['feedback'].append({'decision': decision, 'feedback': feedback, 'at': now(),
                                         'explicit_text_edits': bool(data.get('cue_id') or data.get('subtitles'))})
            self._save_run(run)
            self._remember(key, data, run_id)
            return self.snapshot(run_id)

    def _validate_edits(self, data, narration, plan):
        cue_id, text = data.get('cue_id'), data.get('text')
        cue_edit = None
        if cue_id is not None or text is not None:
            if not narration or not any(cue['id'] == cue_id for cue in narration['cues']):
                raise BridgeError(400, 'invalid_cue', 'cue_id must identify an existing narration cue')
            if not isinstance(text, str) or not text.strip() or len(text) > 4000:
                raise BridgeError(400, 'invalid_text', 'Replacement narration text must contain 1–4000 characters')
            cue_edit = (cue_id, text.strip())
        subtitles = data.get('subtitles', [])
        if not isinstance(subtitles, list) or len(subtitles) > 200:
            raise BridgeError(400, 'invalid_subtitles', 'subtitles must be a list with at most 200 explicit edits')
        seen = set()
        for item in subtitles:
            index = item.get('index') if isinstance(item, dict) else None
            if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < len(plan.get('subtitles', [])) or index in seen:
                raise BridgeError(400, 'invalid_subtitle_index', 'Each subtitle index must identify a distinct existing subtitle')
            if any(not isinstance(item.get(key), str) or not item[key].strip() or len(item[key]) > 2000 for key in ('zh', 'en')):
                raise BridgeError(400, 'invalid_subtitle', 'Each subtitle edit needs nonempty zh and en text')
            seen.add(index)
        return {'cue': cue_edit, 'subtitles': subtitles}

    def cancel(self, job_id):
        with self.lock:
            job = self._job(job_id)
            if job['status'] in ACTIVE:
                job['cancel_requested'] = True
                process = self.processes.get(job_id)
                if process:
                    self._terminate(process)
                if job['status'] == 'queued':
                    job.update(status='cancelled', finished_at=now())
                self._save_job(job)
            return self.job_snapshot(job_id)

    @staticmethod
    def _terminate(process):
        if process.poll() is not None:
            return
        if os.name == 'nt':
            result = subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True, timeout=15)
            if result.returncode and process.poll() is None:
                raise RuntimeError('Unable to stop this task process tree; retry cancellation')
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    def close(self):
        self.stopping.set()
        with self.lock:
            for job in self.jobs.values():
                if job['status'] in ACTIVE:
                    self.cancel(job['job_id'])
        self.tasks.put(None)
        if self.worker:
            self.worker.join(timeout=20)

    def _work(self):
        while not self.stopping.is_set():
            job_id = self.tasks.get()
            if job_id is None:
                return
            self._execute(job_id)

    def _command(self, job, arguments):
        log = self.jobs_dir / (job['job_id'] + '.log')
        environment = os.environ.copy()
        environment.update(PYTHONIOENCODING='utf-8', PYTHONUNBUFFERED='1')
        with log.open('a', encoding='utf-8') as stream:
            stream.write('\n$ ' + subprocess.list2cmdline([str(arg) for arg in arguments]) + '\n')
            stream.flush()
            with self.lock:
                if job['cancel_requested']:
                    raise RuntimeError('Task cancelled')
                kwargs = {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {'start_new_session': True}
                process = subprocess.Popen([str(arg) for arg in arguments], cwd=self.root, env=environment,
                                           stdout=stream, stderr=subprocess.STDOUT, **kwargs)
                self.processes[job['job_id']] = process
            try:
                code = process.wait(timeout=7200)
            except subprocess.TimeoutExpired:
                self._terminate(process)
                process.wait(timeout=20)
                raise RuntimeError('Stage command exceeded the two-hour limit')
            finally:
                with self.lock:
                    self.processes.pop(job['job_id'], None)
            if job['cancel_requested']:
                raise RuntimeError('Task cancelled')
            if code:
                raise RuntimeError(f'Command failed with exit code {code}; see log_tail')

    def _execute(self, job_id):
        with self.lock:
            job = self._job(job_id)
            if job['status'] != 'queued':
                return
            job.update(status='running', started_at=now())
            self._save_job(job)
        try:
            self._perform(job)
            with self.lock:
                if job['cancel_requested']:
                    raise RuntimeError('Task cancelled')
                run = self._run(job['run_id'])
                revision = self._current(run)
                if revision['revision'] != job['revision'] or self._input_hash(revision) != job['input_hash']:
                    raise RuntimeError('Source changed during this stage; rerun it for the current revision')
                job.update(status='succeeded', finished_at=now())
                if job['stage'] == 'preview':
                    revision['preview_input_hash'] = job['input_hash']
                    self._save_run(run)
                job['result'] = self.snapshot(job['run_id'])
                self._save_job(job)
        except Exception as error:
            with self.lock:
                job.update(status='cancelled' if job['cancel_requested'] else 'failed', error=str(error), finished_at=now())
                self._save_job(job)

    def _perform(self, job):
        folder, config, plan = self._episode(job['slug'])
        run = self._run(job['run_id'])
        out = folder / 'build'
        out.mkdir(exist_ok=True)
        cli = [sys.executable, str(self.root / 'vibe.py')]
        stage, slug = job['stage'], job['slug']
        if stage == 'narrate':
            if config.get('narration'):
                tts_cli = os.environ.get('VIBE_TTS_CLI')
                if not tts_cli or not Path(tts_cli).is_file():
                    raise RuntimeError('Set VIBE_TTS_CLI to the installed ttsCN scripts/tts.py before synthesis')
                self._command(job, cli + ['narrate', slug, '--tts-cli', tts_cli])
                self._command(job, ['ffmpeg', '-v', 'error', '-y', '-ss', str(run['preview_start']), '-i', out / 'narration.wav',
                                    '-t', str(run['preview_end'] - run['preview_start']), '-c:a', 'libmp3lame', '-q:a', '3', out / 'narration-preview.mp3'])
            self._command(job, cli + ['mix', slug])
        elif stage == 'preview':
            self._command(job, cli + ['mix', slug])
            self._command(job, cli + ['preview', slug])
            self._command(job, cli + ['render', slug, '--start', str(round(run['preview_start'] * 30)),
                                     '--end', str(round(run['preview_end'] * 30)), '--jobs', '2', '--name', 'draft', '--resume'])
            duration = run['preview_end'] - run['preview_start']
            self._command(job, ['ffmpeg', '-v', 'error', '-y', '-i', out / 'draft.mp4', '-ss', str(run['preview_start']),
                                '-i', out / 'soundtrack.wav', '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy', '-c:a', 'aac',
                                '-b:a', '192k', '-t', str(duration), '-movflags', '+faststart', out / 'preview.mp4'])
            self._command(job, ['ffmpeg', '-v', 'error', '-y', '-ss', str(min(1, duration / 2)), '-i', out / 'preview.mp4',
                                '-frames:v', '1', '-update', '1', out / 'poster.jpg'])
        elif stage == 'render':
            # production_ready is part of the engine's source signature; refresh
            # the geometry audit after explicit approval toggled that flag.
            revision = self._current(run)
            if revision['review_status'] != 'approved' or revision['approved_input_hash'] != self._input_hash(revision):
                raise RuntimeError('Current source is no longer approved')
            self._command(job, cli + ['preview', slug])
            self._command(job, cli + ['render', slug, '--jobs', '2', '--resume'])
        elif stage == 'finalize':
            self._command(job, cli + ['finalize', slug])
        required = {'narrate': ['soundtrack.wav'], 'preview': ['preview.mp4', 'poster.jpg', 'review/layout_audit.json'],
                    'render': ['picture.mp4', 'picture.render.json'], 'finalize': ['final_video.mp4']}[stage]
        if any(not (out / name).is_file() for name in required):
            raise RuntimeError('Stage exited without producing its required artifacts')

    def media(self, raw_path):
        path = unquote(raw_path)
        if not path.startswith('/project/') or '\\' in path or '\x00' in path:
            raise BridgeError(404, 'not_found', 'Resource not found')
        parts = path[len('/project/'):].split('/')
        if any(not part or part in {'.', '..'} or part.startswith('.') or ':' in part for part in parts):
            raise BridgeError(400, 'unsafe_path', 'Invalid resource path')
        allowed = False
        if len(parts) >= 3 and parts[0] == 'videos':
            with self.lock:
                owned = {revision['slug'] for run in self.runs.values() for revision in run['revisions']}
            allowed = parts[1] in owned
        elif len(parts) >= 3 and parts[0] == 'assets' and parts[1] in {'fonts', 'music'}:
            allowed = True
        target = inside(self.root, '/'.join(parts))
        # Check every component: a symlink/junction inside an owned folder must
        # not make another project file publicly readable.
        lexical = self.root
        for part in parts:
            lexical = lexical / part
            if lexical.is_symlink() or lexical.resolve() != lexical.absolute():
                raise BridgeError(403, 'unsafe_path', 'Linked resources are not served')
        if not allowed or target.suffix.lower() not in MEDIA_TYPES or not target.is_file():
            raise BridgeError(404, 'not_found', 'Resource not found')
        return target


class Handler(BaseHTTPRequestHandler):
    server_version = 'VibeLocal/1'

    @property
    def bridge(self):
        return self.server.bridge

    def log_message(self, message, *args):
        # Normal HTTP access logging contains no request bodies or credentials.
        sys.stderr.write('%s %s\n' % (self.log_date_time_string(), message % args))

    def _guard(self):
        hosts = {f'127.0.0.1:{self.bridge.port}', f'localhost:{self.bridge.port}'}
        if self.headers.get('Host', '').lower() not in hosts:
            raise BridgeError(403, 'invalid_host', 'Only the loopback service host is allowed')
        origin = self.headers.get('Origin')
        origins = {f'http://{host}' for host in hosts} | {'http://127.0.0.1:5678', 'http://localhost:5678'}
        if origin and origin not in origins:
            raise BridgeError(403, 'invalid_origin', 'Only the local n8n and bridge origins are allowed')

    def _headers(self, status, content_type, length):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(length))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Cache-Control', 'no-store')
        if self.headers.get('Origin') in {f'http://127.0.0.1:{self.bridge.port}', f'http://localhost:{self.bridge.port}', 'http://127.0.0.1:5678', 'http://localhost:5678'}:
            self.send_header('Access-Control-Allow-Origin', self.headers['Origin'])
            self.send_header('Vary', 'Origin')

    def _json(self, value, status=200):
        payload = json.dumps(value, ensure_ascii=False).encode('utf-8')
        self._headers(status, 'application/json; charset=utf-8', len(payload))
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(payload)

    def _body(self):
        if self.headers.get('Content-Type', '').split(';')[0].strip().lower() != 'application/json':
            raise BridgeError(415, 'json_required', 'Use application/json')
        if self.headers.get('Transfer-Encoding'):
            raise BridgeError(400, 'invalid_body', 'Chunked requests are not supported')
        try:
            length = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            raise BridgeError(400, 'invalid_body', 'Invalid Content-Length')
        if not 0 < length <= MAX_BODY:
            raise BridgeError(413, 'body_limit', 'JSON body must contain 1–131072 bytes')
        try:
            data = json.loads(self.rfile.read(length))
        except (ValueError, UnicodeDecodeError):
            raise BridgeError(400, 'invalid_json', 'Invalid JSON body')
        if not isinstance(data, dict):
            raise BridgeError(400, 'invalid_json', 'Body must be a JSON object')
        return data

    def _file(self, path):
        size = path.stat().st_size
        start, end, status = 0, size - 1, 200
        value = self.headers.get('Range')
        if value:
            match = re.fullmatch(r'bytes=(\d*)-(\d*)', value)
            if not match or not any(match.groups()):
                raise BridgeError(416, 'invalid_range', 'Only one byte range is supported')
            a, b = match.groups()
            if a:
                start, end = int(a), min(int(b), size - 1) if b else size - 1
            else:
                start, end = max(0, size - int(b)), size - 1
            if start > end or start >= size:
                raise BridgeError(416, 'invalid_range', 'Requested range is outside the file')
            status = 206
        content_type = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
        self._headers(status, content_type, end - start + 1)
        self.send_header('Accept-Ranges', 'bytes')
        if status == 206:
            self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        self.end_headers()
        if self.command == 'HEAD':
            return
        with path.open('rb') as stream:
            stream.seek(start)
            remaining = end - start + 1
            while remaining > 0:
                chunk = stream.read(min(65536, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def _dispatch(self):
        self._guard()
        path = urlsplit(self.path).path
        if self.command == 'OPTIONS':
            self._headers(204, 'text/plain', 0)
            self.send_header('Access-Control-Allow-Methods', 'GET, HEAD, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type, Range')
            self.end_headers()
            return
        if self.command in {'GET', 'HEAD'}:
            if path == '/health':
                with self.bridge.lock:
                    active = sum(job['status'] in ACTIVE for job in self.bridge.jobs.values())
                return self._json({'ok': True, 'service': 'vibe-video-bridge', 'version': 1, 'project_root': str(self.bridge.root),
                                   'capabilities': list(STAGES), 'active_jobs': active})
            if path == '/api/episodes':
                return self._json(self.bridge.episodes())
            if path == '/api/runs':
                with self.bridge.lock:
                    recent = sorted(self.bridge.runs.values(), key=lambda item: item['created_at'], reverse=True)[:30]
                    return self._json({'runs': [self.bridge.snapshot(item['run_id']) for item in recent]})
            if re.fullmatch('/api/runs/[a-f0-9]{16}', path):
                return self._json(self.bridge.snapshot(path.split('/')[-1]))
            if re.fullmatch('/api/jobs/[a-f0-9]{16}', path):
                return self._json(self.bridge.job_snapshot(path.split('/')[-1]))
            if path.startswith('/project/'):
                return self._file(self.bridge.media(path))
        if self.command == 'POST':
            data = self._body()
            if path == '/api/runs':
                return self._json(self.bridge.create_run(data), 201)
            match = re.fullmatch(r'/api/runs/([a-f0-9]{16})/(jobs|review)', path)
            if match:
                result = self.bridge.submit(match[1], data) if match[2] == 'jobs' else self.bridge.review(match[1], data)
                return self._json(result, 202 if match[2] == 'jobs' else 200)
            match = re.fullmatch(r'/api/jobs/([a-f0-9]{16})/cancel', path)
            if match:
                return self._json(self.bridge.cancel(match[1]))
        raise BridgeError(404, 'not_found', 'Endpoint not found')

    def _handle(self):
        try:
            self._dispatch()
        except BridgeError as error:
            self._json({'error': {'code': error.code, 'message': str(error)}}, error.status)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except (ValueError, KeyError, TypeError) as error:
            self._json({'error': {'code': 'invalid_configuration', 'message': str(error)}}, 400)
        except Exception as error:
            self.log_error('Bridge error: %s', error)
            self._json({'error': {'code': 'internal_error', 'message': 'Local operation failed; inspect the bridge log'}}, 500)

    do_GET = _handle
    do_HEAD = _handle
    do_POST = _handle
    do_OPTIONS = _handle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=5681)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('port must be between 1024 and 65535')
    # Acquire the listener before recovery touches persisted jobs. A duplicate
    # launch must fail without marking the live service's tasks interrupted.
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    ownership = None
    try:
        ownership = service_lock(Path(__file__).resolve().parents[1])
        bridge = Bridge(port=args.port, recover_interrupted=True)
    except Exception:
        server.server_close()
        if ownership:
            ownership.close()
        raise
    server.daemon_threads = True
    server.bridge = bridge
    print(f'Video bridge: http://127.0.0.1:{args.port}', flush=True)
    try:
        server.serve_forever(poll_interval=.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        bridge.close()
        ownership.close()


if __name__ == '__main__':
    main()
