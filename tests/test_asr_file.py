import json
import wave
from threading import Event

import numpy as np
import pytest

import asr


def write_wav(path, samples, rate=8000):
    with wave.open(str(path), 'wb') as stream:
        stream.setnchannels(samples.shape[1])
        stream.setsampwidth(2)
        stream.setframerate(rate)
        stream.writeframes(samples.astype('<i2').tobytes())


def test_file_is_paced_without_drift_and_flushes_final_result(monkeypatch, tmp_path):
    path = tmp_path / 'speech.wav'
    # Large positive samples catch stereo downmixing that overflows int16.
    write_wav(path, np.full((16000, 2), 30000, dtype=np.int16))
    clock = [100.0]
    waits, blocks, events = [], [], []

    class Stop(Event):
        def wait(self, timeout=None):
            waits.append(timeout)
            clock[0] += timeout
            return self.is_set()

    class Recognizer:
        def SetWords(self, value):
            assert value is True
        def AcceptWaveform(self, data):
            blocks.append(np.frombuffer(data, dtype='<i2'))
            clock[0] += .2  # ASR work must not add .2 s to the next audio deadline.
            return False
        def PartialResult(self):
            return '{"partial": "muzykę"}'
        def FinalResult(self):
            return json.dumps({'text': 'włącz muzykę', 'result': [{'start': .1, 'end': .8}, {'start': 1.1, 'end': 1.8}]})

    monkeypatch.setattr(asr, '_get_model', lambda: None)
    def recognizer(model, rate):
        assert rate == 8000
        return Recognizer()
    monkeypatch.setattr(asr, 'KaldiRecognizer', recognizer)
    monkeypatch.setattr(asr, 'perf_counter', lambda: clock[0])
    text = asr.listen_file(path, Stop(), on_event=lambda kind, **data: events.append((kind, data)))
    assert text == 'włącz muzykę'
    assert waits == pytest.approx([1.0, .8])
    assert len(blocks) == 2 and all(np.all(block == 30000) for block in blocks)
    by_kind = dict(events)
    assert by_kind['speech_start']['at'] == pytest.approx(100.1)
    assert by_kind['speech_end']['at'] == pytest.approx(101.8)
    assert by_kind['transcription_ready']['at'] == pytest.approx(102.2)
    assert by_kind['transcription_ready']['text'] == text


def test_stop_before_file_input_never_opens_file():
    stop = Event()
    stop.set()
    assert asr.listen_file('does-not-exist.mp3', stop) is None


def test_unreadable_and_zero_frame_files_fail_before_loading_model(monkeypatch, tmp_path):
    def unexpected_model_load():
        raise AssertionError('Model must not load for invalid input')
    monkeypatch.setattr(asr, '_get_model', unexpected_model_load)
    bad = tmp_path / 'bad.mp3'
    bad.write_text('not audio')
    with pytest.raises((RuntimeError, OSError)):
        asr.listen_file(bad, Event())
    empty = tmp_path / 'empty.wav'
    write_wav(empty, np.empty((0, 1), dtype=np.int16))
    with pytest.raises(ValueError, match='pust|Pust'):
        asr.listen_file(empty, Event())


def test_file_without_recognized_speech_does_not_produce_empty_transcription(monkeypatch, tmp_path):
    path = tmp_path / 'silence.wav'
    write_wav(path, np.zeros((8, 1), dtype=np.int16))
    class Recognizer:
        def AcceptWaveform(self, data):
            return False
        def PartialResult(self):
            return '{"partial": ""}'
        def FinalResult(self):
            return '{"text": ""}'
    monkeypatch.setattr(asr, '_get_model', lambda: None)
    monkeypatch.setattr(asr, 'KaldiRecognizer', lambda *args: Recognizer())
    with pytest.raises(ValueError, match='rozpoznano mowy'):
        asr.listen_file(path, Event())


def test_shutdown_after_speech_detection_finishes_file_at_natural_speed(monkeypatch, tmp_path):
    path = tmp_path / 'speech.wav'
    write_wav(path, np.zeros((16000, 1), dtype=np.int16))
    clock, slept, blocks = [100.0], [], []
    class Stop(Event):
        def wait(self, timeout=None):
            if not self.is_set():
                clock[0] += timeout
            return self.is_set()
    stop = Stop()
    class Recognizer:
        def AcceptWaveform(self, data):
            blocks.append(data)
            return False
        def PartialResult(self):
            stop.set()
            return '{"partial": "włącz"}'
        def FinalResult(self):
            return '{"text": "włącz muzykę"}'
    def sleep(duration):
        slept.append(duration)
        clock[0] += duration
    monkeypatch.setattr(asr, '_get_model', lambda: None)
    monkeypatch.setattr(asr, 'KaldiRecognizer', lambda *args: Recognizer())
    monkeypatch.setattr(asr, 'perf_counter', lambda: clock[0])
    monkeypatch.setattr(asr, 'sleep', sleep)
    assert asr.listen_file(path, stop) == 'włącz muzykę'
    assert len(blocks) == 2
    assert slept == [1.0]
    assert clock[0] == 102.0


def test_shutdown_before_speech_detection_interrupts_file_without_transcription(monkeypatch, tmp_path):
    path = tmp_path / 'speech.wav'
    write_wav(path, np.zeros((8000, 1), dtype=np.int16))
    class Stop(Event):
        def wait(self, timeout=None):
            self.set()
            return True
    class Recognizer:
        def AcceptWaveform(self, data):
            raise AssertionError('Audio cancelled before it was available')
    monkeypatch.setattr(asr, '_get_model', lambda: None)
    monkeypatch.setattr(asr, 'KaldiRecognizer', lambda *args: Recognizer())
    assert asr.listen_file(path, Stop()) is None


def test_first_nonempty_endpoint_finishes_turn_without_waiting_for_file_tail(monkeypatch, tmp_path):
    path = tmp_path / 'speech-and-long-silence.wav'
    write_wav(path, np.zeros((40000, 1), dtype=np.int16))
    clock, blocks = [100.0], []
    class Stop(Event):
        def wait(self, timeout=None):
            clock[0] += timeout
            return False
    class Recognizer:
        def AcceptWaveform(self, data):
            assert not blocks, 'Audio after the first utterance must not enter this turn'
            blocks.append(data)
            return True
        def Result(self):
            return '{"text": "włącz muzykę"}'
        def FinalResult(self):
            raise AssertionError('An endpoint already finalized this utterance')
    monkeypatch.setattr(asr, '_get_model', lambda: None)
    monkeypatch.setattr(asr, 'KaldiRecognizer', lambda *args: Recognizer())
    monkeypatch.setattr(asr, 'perf_counter', lambda: clock[0])
    assert asr.listen_file(path, Stop()) == 'włącz muzykę'
    assert clock[0] == 101.0
    assert len(blocks) == 1
