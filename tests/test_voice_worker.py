from types import SimpleNamespace

from CarSystem.car_system import CarSystem
from voice_worker import VoiceWorker


def test_voice_worker_sends_microphone_transcription_to_runner(monkeypatch):
    received = {}

    class FakeRunner:
        def __init__(self, car, output_dir, speak_response):
            self.logger = SimpleNamespace(events=[])

        def run_turn(self, transcribe, source):
            received["text"] = transcribe()
            received["source"] = source
            worker.stop_event.set()
            return True

    monkeypatch.setattr("voice_worker.ConversationRunner", FakeRunner)
    monkeypatch.setattr("asr.listen", lambda stop_event: "włącz muzykę")
    worker = VoiceWorker(CarSystem())

    worker.run()

    assert received == {"text": "włącz muzykę", "source": "microphone"}
