from threading import Event
from types import SimpleNamespace

import numpy as np
import pytest
import soundfile as sf

pytestmark = pytest.mark.usefixtures('sounddevice_stub')


def setup_decode(monkeypatch):
    from asr import whisper
    audio_received = []
    class Model:
        def transcribe(self, audio):
            audio_received.append(audio.copy())
            return [SimpleNamespace(text=' Włącz'), SimpleNamespace(text=' muzykę')]
    monkeypatch.setattr(whisper, '_get_model', lambda size: Model())
    return whisper, audio_received


def test_file_resamples_and_paces_preserving_internal_silence(monkeypatch, tmp_path):
    import webrtcvad
    from asr import listen_file
    whisper, received = setup_decode(monkeypatch)
    path = tmp_path / 'speech.wav'
    # 3 voice frames, 2 pause frames, 3 voice frames, 15 silent endpoint frames.
    audio = np.repeat([.5] * 3 + [0] * 2 + [.5] * 3 + [0] * 15, 240)
    sf.write(path, np.column_stack([audio, audio]), 8000, subtype='PCM_16')
    clock = [100.0]
    class Stop(Event):
        def wait(self, timeout=None):
            clock[0] += timeout
            return False
    class Vad:
        def is_speech(self, pcm, rate):
            assert rate == 16000
            return np.mean(np.abs(np.frombuffer(pcm, '<i2'))) > 1000
    monkeypatch.setattr(webrtcvad, 'Vad', lambda mode: Vad())
    monkeypatch.setattr(whisper, 'perf_counter', lambda: clock[0])
    events = []
    assert listen_file(path, Stop(), asr='whisper-small',
                       on_event=lambda kind, **data: events.append((kind, data))) == 'Włącz muzykę'
    assert clock[0] == pytest.approx(100.69)
    assert received[0].dtype == np.float32
    assert len(received[0]) == 11040
    assert np.max(abs(received[0][1800:2100])) < .01  # Original pause survives.
    by_kind = dict(events)
    assert by_kind['speech_start']['at'] == 100
    assert by_kind['speech_end']['at'] == pytest.approx(100.24)
    assert by_kind['transcription_ready']['at'] == pytest.approx(100.69)


def test_whisper_eof_finishes_speech_without_trailing_silence(monkeypatch, tmp_path):
    import webrtcvad
    from asr import listen_file
    whisper, received = setup_decode(monkeypatch)
    path = tmp_path / 'speech.wav'
    sf.write(path, np.ones(1600, dtype=np.float32) / 2, 16000)
    monkeypatch.setattr(webrtcvad, 'Vad', lambda mode: SimpleNamespace(is_speech=lambda pcm, rate: True))
    assert listen_file(path, Event(), asr='whisper-small') == 'Włącz muzykę'
    assert len(received[0]) == 1600


def test_whisper_cancelled_before_input_does_not_load_model(monkeypatch):
    from asr import listen, listen_file
    from asr import whisper
    monkeypatch.setattr(whisper, '_get_model', lambda size: pytest.fail('Model must not load'))
    stop = Event()
    stop.set()
    assert listen(stop, asr='whisper-small') is None
    assert listen_file('missing.mp3', stop, asr='whisper-small') is None


def test_whisper_empty_file_does_not_load_model(monkeypatch, tmp_path):
    from asr import listen_file
    from asr import whisper
    monkeypatch.setattr(whisper, '_get_model', lambda size: pytest.fail('Model must not load'))
    path = tmp_path / 'empty.wav'
    sf.write(path, np.empty(0, dtype=np.float32), 16000)
    with pytest.raises(ValueError, match='Pusty'):
        listen_file(path, Event(), asr='whisper-small')


def test_model_loaded_once_from_local_weights(monkeypatch, tmp_path):
    import pywhispercpp.model
    from asr import whisper
    path = tmp_path / 'ggml-small.bin'
    path.write_bytes(b'weights')
    monkeypatch.setattr(whisper, 'MODELS_DIR', tmp_path)
    monkeypatch.setattr(whisper, '_model', None)
    monkeypatch.setattr(whisper, '_model_name', None)
    loaded = []
    def load(path, **kwargs):
        loaded.append(path)
        return object()
    monkeypatch.setattr(pywhispercpp.model, 'Model', load)
    first = whisper._get_model('small')
    assert whisper._get_model('small') is first
    assert loaded == [str(path)]
    with pytest.raises(FileNotFoundError, match='ggml-medium.bin'):
        whisper._get_model('medium')


def test_microphone_uses_native_rate_and_releases_stream_after_decode(monkeypatch):
    import sounddevice
    import webrtcvad
    from asr import listen
    whisper, received = setup_decode(monkeypatch)
    closed = []
    class Vad:
        def is_speech(self, pcm, rate):
            assert rate == 16000
            return np.mean(np.abs(np.frombuffer(pcm, '<i2'))) > 1000
    class Stream:
        def __init__(self, **kwargs):
            assert kwargs['samplerate'] == 48000
            self.callback = kwargs['callback']
        def __enter__(self):
            timestamp = SimpleNamespace(inputBufferAdcTime=12, currentTime=12)
            self.callback(np.full((14400, 1), .5, dtype=np.float32), 14400, timestamp, None)
            self.callback(np.zeros((48000, 1), dtype=np.float32), 48000, timestamp, None)
        def __exit__(self, *args):
            closed.append(True)
    monkeypatch.setattr(sounddevice, 'query_devices', lambda **kwargs: {'default_samplerate': 48000})
    monkeypatch.setattr(sounddevice, 'InputStream', Stream)
    monkeypatch.setattr(webrtcvad, 'Vad', lambda mode: Vad())
    assert listen(Event(), asr='whisper-small') == 'Włącz muzykę'
    assert len(received) == 1
    assert received[0].dtype == np.float32
    assert closed == [True]


def test_whisper_shutdown_after_speech_finishes_at_natural_speed(monkeypatch, tmp_path):
    import webrtcvad
    from asr import listen_file
    whisper, received = setup_decode(monkeypatch)
    path = tmp_path / 'speech.wav'
    sf.write(path, np.ones(480 * 4, dtype=np.float32) / 2, 16000)
    clock = [100.0]
    class Stop(Event):
        def wait(self, timeout=None):
            if not self.is_set():
                clock[0] += timeout
            return self.is_set()
    stop = Stop()
    class Vad:
        def is_speech(self, pcm, rate):
            stop.set()
            return True
    monkeypatch.setattr(webrtcvad, 'Vad', lambda mode: Vad())
    monkeypatch.setattr(whisper, 'perf_counter', lambda: clock[0])
    monkeypatch.setattr(whisper, 'sleep', lambda duration: clock.__setitem__(0, clock[0] + duration))
    assert listen_file(path, stop, asr='whisper-small') == 'Włącz muzykę'
    assert clock[0] == pytest.approx(100.12)
    assert len(received[0]) == 1920


def test_cancel_during_model_loading_does_not_open_microphone(monkeypatch):
    import sounddevice
    from asr import listen, whisper
    stop = Event()
    def load(size):
        stop.set()
        return object()
    monkeypatch.setattr(whisper, '_get_model', load)
    monkeypatch.setattr(sounddevice, 'query_devices', lambda **kwargs: pytest.fail('Microphone must not open'))
    assert listen(stop, asr='whisper-small') is None
