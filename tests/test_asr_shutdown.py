import json
from threading import Event

import asr


def test_stop_during_partial_transcription_finishes_speech(monkeypatch):
    import sounddevice

    stop = Event()

    class FakeRecognizer:
        def AcceptWaveform(self, data):
            if data == b"start":
                stop.set()
                return False
            return True

        def PartialResult(self):
            return json.dumps({"partial": "włącz"})

        def Result(self):
            return json.dumps({"text": "włącz muzykę"})

    class FakeStream:
        def __init__(self, **kwargs):
            self.callback = kwargs["callback"]

        def __enter__(self):
            self.callback(b"start", 0, None, None)
            self.callback(b"end", 0, None, None)

        def __exit__(self, *args):
            pass

    monkeypatch.setattr(asr, "_get_model", lambda: None)
    monkeypatch.setattr(asr, "KaldiRecognizer", lambda *args: FakeRecognizer())
    monkeypatch.setattr(sounddevice, "query_devices", lambda **kwargs: {"default_samplerate": 16000})
    monkeypatch.setattr(sounddevice, "RawInputStream", FakeStream)

    assert asr.listen(stop) == "włącz muzykę"


def test_stop_before_listening_does_not_open_microphone(monkeypatch):
    import sounddevice

    def unexpected_device_query(**kwargs):
        raise AssertionError("Microphone should not be opened")

    monkeypatch.setattr(sounddevice, "query_devices", unexpected_device_query)
    stop = Event()
    stop.set()

    assert asr.listen(stop) is None


def test_vosk_word_boundaries_use_first_audio_time_after_empty_results(monkeypatch):
    from types import SimpleNamespace
    import sounddevice

    clock = [100.0]
    events = []
    stop = Event()
    class Recognizer:
        def SetWords(self, enabled):
            assert enabled
        def AcceptWaveform(self, data):
            self.data = data
            return True
        def Result(self):
            if self.data == b'silence':
                return '{"text": ""}'
            clock[0] = 104.0
            return json.dumps({'text': 'włącz muzykę', 'result': [{'start': 2.1, 'end': 2.5}, {'start': 2.5, 'end': 3.1}]})
    class Stream:
        def __init__(self, **kwargs):
            self.callback = kwargs['callback']
        def __enter__(self):
            self.callback(b'silence', 16000, SimpleNamespace(currentTime=50, inputBufferAdcTime=49.5), None)
            self.callback(b'words', 16000, SimpleNamespace(currentTime=51, inputBufferAdcTime=50.5), None)
        def __exit__(self, *args):
            pass
    monkeypatch.setattr(asr, 'perf_counter', lambda: clock[0], raising=False)
    monkeypatch.setattr(asr, '_get_model', lambda: None)
    monkeypatch.setattr(asr, 'KaldiRecognizer', lambda *args: Recognizer())
    monkeypatch.setattr(sounddevice, 'query_devices', lambda **kwargs: {'default_samplerate': 16000})
    monkeypatch.setattr(sounddevice, 'RawInputStream', Stream)
    text = asr.listen(stop, on_event=lambda kind, **data: events.append((kind, data)))
    assert text == 'włącz muzykę'
    assert events[0] == ('speech_start', {'at': 101.6})
    assert events[1] == ('speech_end', {'at': 102.6})
    assert events[2] == ('transcription_ready', {'at': 104.0, 'text': text})


def test_asr_without_word_timing_keeps_transcription_and_reports_missing_boundaries(monkeypatch):
    import sounddevice
    events = []
    class Recognizer:
        def SetWords(self, enabled):
            pass
        def AcceptWaveform(self, data):
            return True
        def Result(self):
            return '{"text": "włącz muzykę"}'
    class Stream:
        def __init__(self, **kwargs):
            self.callback = kwargs['callback']
        def __enter__(self):
            self.callback(b'data', 0, None, None)
        def __exit__(self, *args):
            pass
    monkeypatch.setattr(asr, '_get_model', lambda: None)
    monkeypatch.setattr(asr, 'KaldiRecognizer', lambda *args: Recognizer())
    monkeypatch.setattr(sounddevice, 'query_devices', lambda **kwargs: {'default_samplerate': 16000})
    monkeypatch.setattr(sounddevice, 'RawInputStream', Stream)
    assert asr.listen(Event(), on_event=lambda event, **data: events.append(event)) == 'włącz muzykę'
    assert events == ['asr_warning', 'transcription_ready']
