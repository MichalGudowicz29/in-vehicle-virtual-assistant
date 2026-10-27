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
