"""Workflow checks for recorded visual review; these tests do not judge artwork."""

import copy
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import render, visual_review
from tools.project import read_json, write_json


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class VisualReviewContractTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='vibe-visual-review-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.folder = self.root / 'videos' / 'example'
        self.review = self.folder / 'build' / 'review'
        self.review.mkdir(parents=True)
        self.config = {'output': 'build', 'production_ready': True}
        self.signature = 'a' * 64
        self.frame = self.review / '001.000000.png'
        self.motion = self.review / 'transition-sit.jpg'
        # Small fixture bytes are deliberately not creative review of an actual episode.
        self.frame.write_bytes(b'fixture frame: person seated')
        self.motion.write_bytes(b'fixture motion strip: sit, rise, stand')
        self.audit = self.review / 'layout_audit.json'
        write_json(self.audit, {
            'source_sha256': 'b' * 64,
            'visual_source_sha256': self.signature,
            'layout_issue_frames': 0,
            'frames': [{'time': 1.0, 'file': self.frame.name,
                        'sha256': digest(self.frame), 'audit': []}],
            'transition_strips': [{'file': self.motion.name, 'times': [1.0, 1.5, 2.0],
                                   'sha256': digest(self.motion)}],
        })
        self.audit_ref = self.audit.relative_to(self.folder).as_posix()
        self.frame_ref = self.frame.relative_to(self.folder).as_posix()
        self.motion_ref = self.motion.relative_to(self.folder).as_posix()

    def prepare(self, **kwargs):
        self.path = visual_review.prepare_review(
            self.folder, self.config, self.signature, [self.audit_ref], **kwargs)
        return read_json(self.path)

    def passed_record(self, contains_people=True):
        record = self.prepare()
        record.update({'reviewer': 'Fixture reviewer',
                       'scope': 'The seated full-body frame and all three stand-up phases.',
                       'contains_people': contains_people})
        observations = {
            'proportions_structure': 'The head, torso and limb silhouette are coherent in the fixture.',
            'pose_contact': 'The hip rests on the seat and the shoes meet the floor in the fixture.',
            'occlusion_layers': 'The near wrist and the far leg remain distinguishable in the fixture.',
            'composition_readability': 'The whole subject and its relevant contact points remain visible.',
            'motion_continuity': 'The movement retains the same wrist and foot connections across phases.',
            'character_anatomy': 'Both hands have identifiable wrists and the shoulder joins the torso.',
        }
        for name, check in record['checks'].items():
            check.update({'status': 'passed', 'observation': observations[name],
                          'evidence': [self.motion_ref if name == 'motion_continuity' else self.frame_ref]})
        write_json(self.path, record)
        return record

    def validate(self, signature=None):
        return visual_review.validate_review(self.folder, self.config, signature or self.signature)

    def assert_rejected(self, record=None):
        if record is not None:
            write_json(self.path, record)
        report = self.validate()
        self.assertFalse(report['ok'], report)
        self.assertTrue(report['errors'], report)
        with self.assertRaises(ValueError):
            visual_review.require_visual_review(self.folder, self.config, self.signature)

    def test_prepare_is_unreviewed_and_production_flag_cannot_approve_it(self):
        record = self.prepare()
        self.assertEqual((self.review / 'visual-review.json').resolve(), Path(self.path).resolve())
        self.assertEqual(1, record['schema_version'])
        self.assertEqual(self.signature, record['visual_source_sha256'])
        self.assertEqual('', record['reviewer'])
        self.assertIsNone(record['contains_people'])
        self.assertEqual({'proportions_structure', 'pose_contact', 'occlusion_layers',
                          'composition_readability', 'motion_continuity', 'character_anatomy'},
                         set(record['checks']))
        self.assertTrue(all(check['status'] == 'unreviewed' for check in record['checks'].values()))
        self.assertEqual({self.frame_ref, self.motion_ref}, {entry['path'] for entry in record['evidence']})
        self.assertEqual([self.audit_ref], [entry['path'] for entry in record['evidence_reports']])
        self.assertRegex(record['evidence_reports'][0]['sha256'], r'^[a-f0-9]{64}$')
        self.assert_rejected()

    def test_current_specific_review_passes_and_requires_all_checks(self):
        record = self.passed_record()
        self.assertTrue(self.validate()['ok'])
        self.assertTrue(visual_review.require_visual_review(
            self.folder, self.config, self.signature)['ok'])
        for missing in record['checks']:
            with self.subTest(missing=missing):
                changed = copy.deepcopy(record)
                del changed['checks'][missing]
                self.assert_rejected(changed)

    def test_unreviewed_and_revision_findings_cannot_be_hidden_by_other_passes(self):
        record = self.passed_record()
        for name in record['checks']:
            for state in ('unreviewed', 'needs_revision'):
                with self.subTest(check=name, state=state):
                    changed = copy.deepcopy(record)
                    changed['checks'][name]['status'] = state
                    self.assert_rejected(changed)

    def test_reviewer_scope_people_and_observed_evidence_are_required(self):
        record = self.passed_record()
        cases = [('reviewer', ''), ('scope', '  '), ('contains_people', None),
                 ('contains_people', 'false'), ('contains_people', 0)]
        for name, value in cases:
            with self.subTest(field=name, value=value):
                changed = copy.deepcopy(record)
                changed[name] = value
                self.assert_rejected(changed)
        for field, value in [('observation', '  '), ('evidence', []),
                             ('evidence', ['build/review/unregistered.png'])]:
            with self.subTest(check_field=field):
                changed = copy.deepcopy(record)
                changed['checks']['proportions_structure'][field] = value
                self.assert_rejected(changed)

    def test_motion_needs_multiple_phases_and_anatomy_needs_full_size_frames(self):
        audit = read_json(self.audit)
        frame_refs = [self.frame_ref]
        for seconds in (1.5, 2.0):
            frame = self.review / f'{seconds:.6f}.png'
            frame.write_bytes(f'fixture phase at {seconds}'.encode('utf-8'))
            audit['frames'].append({'time': seconds, 'file': frame.name,
                                    'sha256': digest(frame), 'audit': []})
            frame_refs.append(frame.relative_to(self.folder).as_posix())
        write_json(self.audit, audit)
        record = self.passed_record()
        for refs in ([self.frame_ref], [self.frame_ref] * 3, frame_refs[:2]):
            with self.subTest(phases=refs):
                changed = copy.deepcopy(record)
                changed['checks']['motion_continuity']['evidence'] = refs
                self.assert_rejected(changed)
        record['checks']['motion_continuity']['evidence'] = frame_refs
        write_json(self.path, record)
        self.assertTrue(self.validate()['ok'])
        for name in ('proportions_structure', 'character_anatomy'):
            with self.subTest(check=name):
                changed = copy.deepcopy(record)
                changed['checks'][name]['evidence'] = [self.motion_ref]
                self.assert_rejected(changed)

    def test_not_applicable_requires_reason_and_does_not_skip_general_visual_quality(self):
        record = self.passed_record(contains_people=False)
        record['checks']['character_anatomy'].update({
            'status': 'not_applicable',
            'observation': 'This fixture contains geometric objects and no people.',
            'evidence': [self.frame_ref],
        })
        write_json(self.path, record)
        self.assertTrue(self.validate()['ok'])
        for name in ('proportions_structure', 'occlusion_layers', 'composition_readability'):
            with self.subTest(check=name):
                changed = copy.deepcopy(record)
                changed['checks'][name]['status'] = 'not_applicable'
                self.assert_rejected(changed)
        changed = copy.deepcopy(record)
        changed['contains_people'] = True
        self.assert_rejected(changed)
        changed = copy.deepcopy(record)
        changed['checks']['character_anatomy']['observation'] = ''
        self.assert_rejected(changed)

    def test_changes_to_visual_source_report_or_images_invalidate_prior_review(self):
        record = self.passed_record()
        self.assertFalse(self.validate('c' * 64)['ok'])
        for changed_path in (self.frame, self.motion, self.audit):
            with self.subTest(changed=changed_path.name):
                original = changed_path.read_bytes()
                changed_path.write_bytes(original + b' changed after review')
                self.assert_rejected(record)
                changed_path.write_bytes(original)
        self.assertTrue(self.validate()['ok'])

    def test_preview_report_can_refresh_encoded_signature_without_invalidating_visual_review(self):
        self.passed_record()
        audit = read_json(self.audit)
        audit['source_sha256'] = 'd' * 64
        # This is the report change caused by setting production_ready and rerunning preview.
        self.audit.write_text(json.dumps(dict(reversed(list(audit.items())))), encoding='utf-8')
        self.assertTrue(self.validate()['ok'])
        audit['layout_issue_frames'] = 1
        write_json(self.audit, audit)
        self.assert_rejected()

    def test_missing_or_malformed_review_fails_closed(self):
        self.assert_rejected()
        self.path = self.review / 'visual-review.json'
        for content in ('{broken JSON', '[]', '{"schema_version": 999}'):
            with self.subTest(content=content):
                self.path.write_text(content, encoding='utf-8')
                self.assert_rejected()

    def test_prepare_refuses_stale_reports_changed_images_or_no_frame(self):
        original = read_json(self.audit)
        cases = []
        stale = copy.deepcopy(original)
        stale['visual_source_sha256'] = 'c' * 64
        cases.append(stale)
        old = copy.deepcopy(original)
        del old['visual_source_sha256']
        cases.append(old)
        changed_image = copy.deepcopy(original)
        changed_image['frames'][0]['sha256'] = 'c' * 64
        cases.append(changed_image)
        no_frame = copy.deepcopy(original)
        no_frame['frames'] = []
        cases.append(no_frame)
        for audit in cases:
            with self.subTest(audit=audit):
                write_json(self.audit, audit)
                with self.assertRaises(ValueError):
                    self.prepare()
                self.assertFalse((self.review / 'visual-review.json').exists())

    def test_replace_preserves_previous_review_and_resets_decisions(self):
        self.passed_record()
        previous = Path(self.path).read_bytes()
        with self.assertRaises((ValueError, FileExistsError)):
            self.prepare()
        self.assertEqual(previous, Path(self.path).read_bytes())
        record = self.prepare(replace=True)
        backups = [path for path in self.review.rglob('*')
                   if path.is_file() and path.resolve() != Path(self.path).resolve()
                   and path.read_bytes() == previous]
        self.assertTrue(backups, 'Replacing review must retain the prior review for inspection')
        self.assertTrue(all(check['status'] == 'unreviewed' for check in record['checks'].values()))
        self.assert_rejected()

    def test_episode_test_only_flag_does_not_bypass_review(self):
        self.config['test_only'] = True
        with patch.object(visual_review, 'ROOT', self.root):
            self.assert_rejected()
            technical = self.root / '.local' / 'self-test-fixture'
            technical.mkdir(parents=True)
            result = visual_review.require_visual_review(technical, self.config, self.signature)
            self.assertTrue(result['ok'])
            for bad_folder, config in [
                    (self.root / 'videos' / 'self-test-fixture', self.config),
                    (self.root / '.local' / 'ordinary-film', self.config),
                    (technical, {**self.config, 'test_only': False}),
                    (technical, {**self.config, 'test_only': 'true'}),
            ]:
                with self.subTest(folder=bad_folder, config=config):
                    bad_folder.mkdir(parents=True, exist_ok=True)
                    with self.assertRaises(ValueError):
                        visual_review.require_visual_review(bad_folder, config, self.signature)

    def test_all_formal_entry_points_reject_missing_or_failed_review_before_encoding(self):
        import vibe
        from tools import finalize as finalizer
        from tools import video_review

        plan = {'duration': 1, 'fps': 30, 'frames': 30, 'impact_frame': 15}
        technical_signature = 'b' * 64
        write_json(self.folder / 'build/picture.render.json', {
            'start': 0, 'frames': 30, 'source_sha256': technical_signature})
        configured_renderer = SimpleNamespace(
            ROOT=self.folder, OUT=self.folder / 'build',
            source_signature=lambda: technical_signature,
            visual_source_signature=lambda: self.signature)
        for state in ('missing', 'needs_revision'):
            with self.subTest(state=state):
                if state == 'needs_revision':
                    record = self.passed_record()
                    record['checks']['pose_contact']['status'] = state
                    write_json(self.path, record)
                # The old requirements (production_ready + current successful layout) pass.
                with self.assertRaisesRegex(ValueError, '视觉审核'):
                    vibe.require_review(configured_renderer, self.config)
                with patch.object(video_review, 'load', return_value=(self.folder, self.config, plan)), \
                        patch.object(video_review.render, 'visual_source_signature', return_value=self.signature), \
                        patch.object(video_review, 'mix_with_receipt') as mix, \
                        patch.object(video_review.subprocess, 'run') as run:
                    with self.assertRaisesRegex(ValueError, '视觉审核'):
                        video_review.finalize('example')
                    mix.assert_not_called()
                    run.assert_not_called()
                with patch.object(finalizer, 'visual_source_signature', return_value=self.signature), \
                        patch.object(finalizer.subprocess, 'run') as run:
                    with self.assertRaisesRegex(ValueError, '视觉审核'):
                        finalizer.finalize(self.folder, self.config, plan, technical_signature)
                    run.assert_not_called()
                self.assertFalse((self.folder / 'build/final_video.mp4').exists())


class VisualSourceSignatureTests(unittest.TestCase):
    def test_production_state_and_json_format_do_not_invalidate_visuals_but_sources_do(self):
        with tempfile.TemporaryDirectory(prefix='vibe-visual-signature-') as temporary:
            root = Path(temporary)
            config = {'production_ready': False, 'entry': 'index.html', 'preview_times': [0, 1]}
            write_json(root / 'film.json', config)
            for name in ('index.html', 'scenes.js', 'font.ttf'):
                (root / name).write_bytes(name.encode('utf-8'))
            names = ['film.json', 'index.html', 'scenes.js', 'font.ttf']
            with patch.object(render, 'ROOT', root), patch.object(render, 'SOURCE_NAMES', names):
                visual_before = render.visual_source_signature()
                encoded_before = render.source_signature()
                config['production_ready'] = True
                write_json(root / 'film.json', config)
                self.assertEqual(visual_before, render.visual_source_signature())
                self.assertNotEqual(encoded_before, render.source_signature())
                (root / 'film.json').write_text(json.dumps(dict(reversed(list(config.items())))), encoding='utf-8')
                self.assertEqual(visual_before, render.visual_source_signature())
                for name in ('index.html', 'scenes.js', 'font.ttf'):
                    with self.subTest(source=name):
                        path = root / name
                        original = path.read_bytes()
                        path.write_bytes(original + b'changed')
                        self.assertNotEqual(visual_before, render.visual_source_signature())
                        path.write_bytes(original)
                config['preview_times'] = [0, 2]
                write_json(root / 'film.json', config)
                self.assertNotEqual(visual_before, render.visual_source_signature())


if __name__ == '__main__':
    unittest.main()
