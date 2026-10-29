"""Built-in Edge synthesis; network audio is converted to the project's PCM format."""

import asyncio
import importlib.metadata
from pathlib import Path
import subprocess
import tempfile
import wave


def synthesize_edge(text, target, voice='zh-CN-YunjianNeural', rate='+0%'):
    try:
        import edge_tts
    except ImportError as error:
        raise RuntimeError('Missing edge-tts. Run python bootstrap.py first.') from error
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.edge-', dir=target.parent) as temporary:
        mp3, wav = Path(temporary) / 'speech.mp3', Path(temporary) / 'speech.wav'

        async def receive():
            boundaries = []
            speech = edge_tts.Communicate(text, voice, rate=rate, boundary='WordBoundary',
                                          connect_timeout=15, receive_timeout=45)
            with mp3.open('wb') as stream:
                async for event in speech.stream():
                    if event['type'] == 'audio':
                        stream.write(event['data'])
                    elif event['type'] == 'WordBoundary':
                        boundaries.append({'text': event['text'],
                                           'offset_sec': event['offset'] / 10_000_000,
                                           'duration_sec': event['duration'] / 10_000_000})
            if not mp3.stat().st_size:
                raise RuntimeError('Edge returned no audio')
            return boundaries

        try:
            boundaries = asyncio.run(asyncio.wait_for(receive(), timeout=120))
        except Exception as error:
            raise RuntimeError(f'Edge synthesis failed ({type(error).__name__}). Check network access and retry; existing cache is preserved.') from error
        converted = subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(mp3),
                                    '-ac', '1', '-ar', '44100', '-c:a', 'pcm_s16le', str(wav)],
                                   capture_output=True, timeout=45)
        if converted.returncode:
            raise RuntimeError('FFmpeg could not decode the synthesized Edge audio')
        with wave.open(str(wav), 'rb') as stream:
            duration = stream.getnframes() / stream.getframerate()
        if duration <= 0:
            raise RuntimeError('Edge returned an empty waveform')
        wav.replace(target)
    return {'word_boundaries': boundaries, 'duration': duration,
            'synthesis_adapter': 'builtin-edge', 'edge_tts_version': importlib.metadata.version('edge-tts')}
