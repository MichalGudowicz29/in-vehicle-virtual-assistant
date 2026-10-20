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
