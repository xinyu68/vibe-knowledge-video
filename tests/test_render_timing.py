import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path
from unittest.mock import Mock, patch


class RenderTimingTests(unittest.TestCase):
    def test_parallel_segment_join_keeps_every_frame_on_the_30fps_grid(self):
        for command in ['ffmpeg', 'ffprobe']:
            if not shutil.which(command):
                self.skipTest(f'Install {command} to check encoded frame timestamps')
        if importlib.util.find_spec('playwright') is None:
            self.skipTest('Install project requirements to import the renderer')
        from tools import render

        temporary = tempfile.TemporaryDirectory(prefix='vibe-render-timing-')
        output = Path(temporary.name).resolve()
        self.assertEqual(Path(tempfile.gettempdir()).resolve(), output.parent)
        try:
            # Render uses 23, 23, 22, 23 frames. Their durations do not fit a
            # millisecond grid, exposing drift if concat offsets are rounded.
            frame_count = 91

            def encoded_part(start, end, index, url, name, signature):
                target = render.part_path(name, start, end, index)
                subprocess.run([
                    'ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                    'color=c=navy:s=64x64:r=30', '-frames:v', str(end - start),
                    '-an', '-c:v', 'libx264', '-preset', 'fast', '-crf', '17',
                    '-threads', '1', '-pix_fmt', 'yuv420p', '-movflags',
                    '+faststart', str(target),
                ], check=True, capture_output=True)
                return target

            # Only browser frame production is substituted. Exercise the actual
            # partitioning, concat list, FFmpeg join and render metadata path.
            with patch.object(render, 'OUT', output), \
                    patch.object(render, 'FPS', 30), \
                    patch.object(render, 'FRAMES', frame_count), \
                    patch.object(render, 'source_signature', return_value='test-source'), \
                    patch.object(render, 'server', return_value=(Mock(), 'unused')), \
                    patch.object(render, 'part', side_effect=encoded_part):
                render.render(0, frame_count, 4, 'timing')

            probe = subprocess.run([
                'ffprobe', '-v', 'error', '-select_streams', 'v:0',
                '-show_frames', '-show_entries',
                'stream=nb_frames,r_frame_rate,avg_frame_rate,time_base:'
                'frame=best_effort_timestamp', '-of', 'json',
                str(output / 'timing.mp4'),
            ], check=True, capture_output=True, encoding='utf-8')
            data = json.loads(probe.stdout)
            stream = data['streams'][0]
            self.assertEqual(frame_count, int(stream['nb_frames']))
            self.assertEqual(Fraction(30), Fraction(stream['r_frame_rate']))
            self.assertEqual(Fraction(30), Fraction(stream['avg_frame_rate']))
            timestamps = [int(frame['best_effort_timestamp'])
                          for frame in data['frames']]
            self.assertEqual(frame_count, len(timestamps))
            time_base = Fraction(stream['time_base'])
            frame_tick = Fraction(1, 30) / time_base
            self.assertEqual(1, frame_tick.denominator)
            # Check every decoded frame, including the three join boundaries.
            self.assertEqual([index * int(frame_tick) for index in range(frame_count)],
                             timestamps)
            self.assertEqual({int(frame_tick)},
                             {later - earlier for earlier, later
                              in zip(timestamps, timestamps[1:])})
        finally:
            temporary.cleanup()


if __name__ == '__main__':
    unittest.main()
