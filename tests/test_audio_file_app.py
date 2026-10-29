"""CLI/Qt integration without microphone, paid LLM calls or physical playback."""

import json
import os
from pathlib import Path
import subprocess
import sys
import wave


def test_cli_file_turn_finishes_after_response_and_writes_report(tmp_path):
    path = tmp_path / 'speech.wav'
    with wave.open(str(path), 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(bytes(16000 * 2))
    output = tmp_path / 'reports'
    script = '''
import json
from pathlib import Path
import runpy
import sys
import asr
import voice_worker
from session_report import SessionReport

wav_path, output = sys.argv[1:]
class Recognizer:
    def SetWords(self, value):
        pass
    def AcceptWaveform(self, data):
        return False
    def PartialResult(self):
        return '{"partial": "włącz"}'
    def FinalResult(self):
        return json.dumps({'text': 'włącz muzykę', 'result': [{'start': .1, 'end': .8}]})
asr._get_model = lambda: None
asr.KaldiRecognizer = lambda *args: Recognizer()
def forbidden_microphone(*args, **kwargs):
    raise AssertionError('Microphone must not be used')
asr.listen = forbidden_microphone

class Assistant:
    def __init__(self, car):
        self.car = car
    def handle_text(self, text, *, report, turn_id):
        assert text == 'włącz muzykę'
        report.emit('agent_start', turn_id=turn_id)
        assert self.car.music.next_track() is True
        report.emit('agent_end', turn_id=turn_id, success=True, text='Gotowe')
        return 'Gotowe'
voice_worker.Assistant = Assistant
def speak(text, on_event):
    assert text == 'Gotowe'
    for event in ['tts_start', 'tts_end', 'audio_start', 'audio_end']:
        on_event(event)
voice_worker.VoiceWorker._speak_response = staticmethod(speak)
original_save = SessionReport.save
SessionReport.save = lambda self: original_save(self, Path(output))
sys.argv = ['main.py', '--audio-file', wav_path]
runpy.run_path('main.py', run_name='__main__')
'''
    result = subprocess.run([sys.executable, '-c', script, str(path), str(output)],
                            env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen', 'SDL_AUDIODRIVER': 'dummy'},
                            text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    reports = list(output.glob('*.json'))
    assert len(reports) == 1
    data = json.loads(reports[0].read_text())
    assert data['input_source'] == {'type': 'audiofile', 'path': str(path.resolve())}
    assert data['counts'] == {'completed': 1, 'failed': 0, 'interrupted': 0}
    assert data['metrics']['Czas mowy']['mean_s'] > .69
    history = [e for e in data['events'] if e['turn_id'] == 1]
    assert history[-2]['type'] == 'audio_end'
    assert history[-1]['type'] == 'turn_end'
    assert 'Wejście: audiofile' in reports[0].with_suffix('.txt').read_text()
    assert 'Application exiting' in result.stdout


def test_cli_rejects_missing_file_before_starting_application(tmp_path):
    path = tmp_path / 'missing.mp3'
    result = subprocess.run([sys.executable, 'main.py', '--audio-file', str(path)],
                            text=True, capture_output=True, timeout=20)
    assert result.returncode == 2
    assert 'Nie znaleziono pliku audio' in result.stderr
    assert 'Starting assistant thread' not in result.stdout
