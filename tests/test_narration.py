import tempfile
import unittest
from pathlib import Path

import numpy as np

from tools.narration import SR, duck_envelope, settings
from tools.project import write_json


class NarrationTests(unittest.TestCase):
    def test_empty_narrated_scaffold_requires_real_content(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            write_json(folder/'narration.json', {'music_mode': 'constant', 'cues': []})
            with self.assertRaisesRegex(ValueError, 'cues'):
                settings(folder, {'narration': 'narration.json'}, {'duration': 159.25})

    def test_rejects_voice_over_music_impact_and_overlapping_cues(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            script = {'cues': [{'id': '01', 'start': 1., 'end': 3., 'text': '测试'}],
                      'protected_gaps': [[2., 2.5]]}
            write_json(folder/'narration.json', script)
            with self.assertRaisesRegex(ValueError, 'protected music'):
                settings(folder, {'narration': 'narration.json'}, {'duration': 10})
            script['protected_gaps'] = []
            script['cues'].append({'id': '02', 'start': 2.9, 'end': 4., 'text': '重叠'})
            write_json(folder/'narration.json', script)
            with self.assertRaisesRegex(ValueError, 'overlapping'):
                settings(folder, {'narration': 'narration.json'}, {'duration': 10})

    def test_constant_music_is_unchanged_at_voice_boundaries_and_impact(self):
        report = {'music_mode': 'constant', 'duck_db': -14, 'attack': .18, 'release': .38,
                  'protected_gaps': [[16.4, 17.9]],
                  'cues': [{'start': .25, 'actual_end': 2.97},
                           {'start': 13.05, 'actual_end': 15.59},
                           {'start': 18.08, 'actual_end': 20.41}]}
        envelope = duck_envelope(round(25*SR), report)
        np.testing.assert_array_equal(envelope, np.ones(round(25*SR), dtype=np.float32))

    def test_legacy_duck_envelope_remains_available_when_explicitly_used(self):
        report = {'duck_db': -11, 'attack': .18, 'release': .38,
                  'protected_gaps': [[16.4, 17.9]],
                  'cues': [{'start': 13.05, 'actual_end': 16.0},
                           {'start': 18.08, 'actual_end': 20.4},
                           {'start': 20.5, 'actual_end': 22.} ]}
        envelope = duck_envelope(round(25*SR), report)
        self.assertTrue(np.all(envelope[round(16.4*SR):round(17.9*SR)] == 1))
        self.assertAlmostEqual(10**(-11/20), float(envelope[round(19*SR)]), places=6)
        self.assertLess(float(envelope[round(20.45*SR)]), .5)
        self.assertTrue(np.all(envelope[round(23*SR):] == 1))
        self.assertLess(float(np.max(np.abs(np.diff(envelope)))), .0002)


if __name__ == '__main__':
    unittest.main()
