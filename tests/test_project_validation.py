from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import project


class PlanGenerationTests(unittest.TestCase):
    def test_invalid_edits_preserve_last_generated_plan_and_valid_new_projects_generate_it(self):
        with tempfile.TemporaryDirectory(prefix='vibe-project-validation-') as temporary:
            root = Path(temporary)
            folder = root / 'videos/demo'
            folder.mkdir(parents=True)
            (folder / 'index.html').write_text('<canvas></canvas>', encoding='utf-8')
            config = {'entry': 'index.html', 'sources': ['index.html', 'plan.js']}
            plan = {'duration': 1, 'fps': 30, 'frames': 30, 'impact_frame': 15}
            project.write_json(folder / 'film.json', config)
            project.write_json(folder / 'plan.json', plan)
            with patch.object(project, 'ROOT', root):
                project.load('demo')
                previous = (folder / 'plan.js').read_bytes()
                plan['subtitles'] = [{'start': .5, 'end': 2, 'zh': 'invalid', 'en': 'invalid'}]
                project.write_json(folder / 'plan.json', plan)
                with self.assertRaises(ValueError):
                    project.load('demo')
                self.assertEqual(previous, (folder / 'plan.js').read_bytes())
                plan.pop('subtitles')
                plan['title'] = 'Updated'
                project.write_json(folder / 'plan.json', plan)
                project.load('demo')
                self.assertNotEqual(previous, (folder / 'plan.js').read_bytes())


if __name__ == '__main__':
    unittest.main()
