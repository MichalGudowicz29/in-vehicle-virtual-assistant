from CarSystem.car_system import CarSystem
from voice_worker import VoiceWorker


def test_voice_worker_sends_microphone_transcription_to_assistant(monkeypatch):
    received = {}

    class FakeAssistant:
        def __init__(self, car):
            pass

        def handle_text(self, text):
            received["text"] = text
            worker.stop_event.set()
            return ""

    monkeypatch.setattr("voice_worker.Assistant", FakeAssistant)
    monkeypatch.setattr("asr.listen", lambda stop_event: "włącz muzykę")
    worker = VoiceWorker(CarSystem())

    worker.run()

    assert received == {"text": "włącz muzykę"}


def test_stop_finishes_response_before_signalling_finished(monkeypatch):
    actions = []

    class FakeAssistant:
        def __init__(self, car):
            pass

        def handle_text(self, text):
            worker.stop()
            return "Gotowe"

    monkeypatch.setattr("voice_worker.Assistant", FakeAssistant)
    monkeypatch.setattr("asr.listen", lambda stop_event: "włącz muzykę")
    worker = VoiceWorker(None)
    monkeypatch.setattr(worker, "_speak_response", lambda text: actions.append(text))
    worker.finished.connect(lambda: actions.append("finished"))

    worker.run()

    assert actions == ["Gotowe", "finished"]


def test_finished_is_emitted_also_when_assistant_fails(monkeypatch):
    import pytest

    def fail(car):
        raise RuntimeError("Cannot initialize assistant")

    monkeypatch.setattr("voice_worker.Assistant", fail)
    worker = VoiceWorker(None)
    finished = []
    worker.finished.connect(lambda: finished.append(True))

    with pytest.raises(RuntimeError):
        worker.run()

    assert finished == [True]
