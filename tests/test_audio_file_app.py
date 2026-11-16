"""CLI/Qt integration without microphone, paid LLM calls or physical playback."""

import json
import os
from pathlib import Path
import subprocess
import sys
import wave

import pytest


@pytest.mark.parametrize(('experiment', 'override', 'expected', 'reasoning', 'expected_reasoning'), [
    (False, None, 'whisper-small', '', False),
    (False, 'vosk', 'vosk', '', False),
    (True, None, 'vosk', '', None),
    (False, None, 'whisper-small', 'true', True),
])
def test_cli_selects_manual_whisper_default_and_preserves_experiment_config(
        tmp_path, music_file, experiment, override, expected, reasoning, expected_reasoning):
    path = tmp_path / 'speech.wav'
    path.touch()
    output = tmp_path / 'reports'
    script = '''
import runpy
import sys
import pygame
import asr
import voice_worker
import config

music_file, output, audio_file, experiment, override, expected, expected_reasoning = sys.argv[1:]
load = pygame.mixer.music.load
pygame.mixer.music.load = lambda path: load(music_file)
voice_worker.Assistant = lambda car: None
def listen(*args, **kwargs):
    assert kwargs['asr'] == expected, kwargs['asr']
    assert str(config.LLM_GENERATION['reasoning']) == expected_reasoning
    print('LISTENING', flush=True)
    return None
asr.listen = asr.listen_file = listen
sys.argv = ['main.py', '--report-dir', output]
if experiment == 'True':
    sys.argv.extend(['--experiment', '--audio-file', audio_file])
if override != 'None':
    sys.argv.extend(['--asr', override])
runpy.run_path('main.py', run_name='__main__')
'''
    result = subprocess.run(
        [sys.executable, '-c', script, str(music_file), str(output), str(path),
         str(experiment), str(override), expected, str(expected_reasoning)],
        env={**os.environ, 'ASR_MODEL': 'vosk', 'QT_QPA_PLATFORM': 'offscreen',
             'SDL_AUDIODRIVER': 'dummy', 'OLLAMA_REASONING': reasoning}, text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert f'ASR: {expected}' in result.stdout
    assert result.stdout.index(f'ASR: {expected}') < result.stdout.index('LISTENING')
    data = json.loads(next(output.glob('*.json')).read_text())
    assert data['models']['asr'].startswith('Whisper small' if expected == 'whisper-small' else 'Vosk')


@pytest.mark.parametrize('asr_model', ['vosk', 'whisper-small'])
@pytest.mark.parametrize('experiment', [False, True])
def test_cli_file_turn_finishes_after_response_and_writes_report(tmp_path, music_file, asr_model, experiment):
    path = tmp_path / 'speech.wav'
    with wave.open(str(path), 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(bytes(16000 * 2))
    output = tmp_path / 'Konfiguracja1_Zadanie1' / 'raporty sesji'
    script = '''
import json
from pathlib import Path
import runpy
import sys
import pygame
import asr
import asr.vosk as vosk
import voice_worker
import session_controls

wav_path, output, music_file, asr_model, experiment = sys.argv[1:]
OriginalControls = session_controls.SessionControls
class Controls(OriginalControls):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        assert self.touchEnabled is (experiment != 'True')
        if experiment == 'True':
            checkpoints = list(Path(output).glob('session_*.json'))
            assert len(checkpoints) == 1
            assert json.loads(checkpoints[0].read_text())['ended_at'] is None
session_controls.SessionControls = Controls
load = pygame.mixer.music.load
pygame.mixer.music.load = lambda _path: load(music_file)
class Recognizer:
    def SetWords(self, value):
        pass
    def AcceptWaveform(self, data):
        return False
    def PartialResult(self):
        return '{"partial": "włącz"}'
    def FinalResult(self):
        return json.dumps({'text': 'włącz muzykę', 'result': [{'start': .1, 'end': .8}]})
vosk._get_model = lambda: None
vosk.KaldiRecognizer = lambda *args: Recognizer()
def forbidden_microphone(*args, **kwargs):
    raise AssertionError('Microphone must not be used')
asr.listen = forbidden_microphone
if asr_model != 'vosk':
    from types import SimpleNamespace
    from asr import whisper
    import webrtcvad
    whisper._get_model = lambda size: SimpleNamespace(transcribe=lambda audio: [SimpleNamespace(text='włącz muzykę')])
    webrtcvad.Vad = lambda mode: SimpleNamespace(is_speech=lambda pcm, rate: True)

class Assistant:
    def __init__(self, car):
        self.car = car
        assert car.music.currentTrackIndex == (1 if experiment == 'True' else 0)
        assert car.music.isPlaying is False
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
sys.argv = ['main.py', '--audio-file', wav_path, '--report-dir', output, '--asr', asr_model]
if experiment == 'True':
    sys.argv.append('--experiment')
runpy.run_path('main.py', run_name='__main__')
'''
    result = subprocess.run([sys.executable, '-c', script, str(path), str(output), str(music_file), asr_model, str(experiment)],
                            env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen', 'SDL_AUDIODRIVER': 'dummy'},
                            text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    reports = list(output.glob('*.json'))
    assert len(reports) == 1
    data = json.loads(reports[0].read_text())
    assert data['input_source'] == {'type': 'audiofile', 'path': str(path.resolve())}
    assert data['models']['asr'].startswith('Vosk' if asr_model == 'vosk' else 'Whisper small')
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


def test_cli_rejects_report_directory_that_is_a_file(tmp_path):
    path = tmp_path / 'occupied'
    path.write_text('keep me')
    result = subprocess.run([sys.executable, 'main.py', '--report-dir', str(path)],
                            text=True, capture_output=True, timeout=20)
    assert result.returncode == 2
    assert 'Nie można przygotować folderu raportów' in result.stderr
    assert path.read_text() == 'keep me'
    assert 'Starting assistant thread' not in result.stdout


def test_cli_rejects_unknown_asr_before_starting_application():
    result = subprocess.run([sys.executable, 'main.py', '--asr', 'whisper-typo'],
                            text=True, capture_output=True, timeout=20)
    assert result.returncode == 2
    assert 'invalid choice' in result.stderr
    assert 'Starting assistant thread' not in result.stdout


def test_experiment_mode_requires_audio_file_before_starting_application():
    result = subprocess.run([sys.executable, 'main.py', '--experiment'],
                            text=True, capture_output=True, timeout=20)
    assert result.returncode == 2
    assert '--audio-file' in result.stderr
    assert 'Starting assistant thread' not in result.stdout
