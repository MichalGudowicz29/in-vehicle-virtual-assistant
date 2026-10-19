from CarSystem.car_system import CarSystem
from evaluation.conversation_runner import ConversationRunner


def test_runner_records_file_metadata_and_transcription(tmp_path, monkeypatch):
    class FakeAssistant:
        def __init__(self, car):
            self.execution_events = []

        def handle_text(self, text, turn_id=None):
            assert text == "nawiguj do domu"
            assert turn_id is not None
            return "Gotowe"

    monkeypatch.setattr("evaluation.conversation_runner.Assistant", FakeAssistant)
    spoken = []
    runner = ConversationRunner(
        CarSystem(),
        tmp_path,
        speak_response=spoken.append,
    )

    result = runner.run_turn(
        lambda: "nawiguj do domu",
        source="audio_file",
        reference_text="nawiguj do domu",
        audio_path="samples/1.wav",
    )

    assert result is True
    assert spoken == ["Gotowe"]
    assert any(
        event["type"] == "asr_finished"
        and event["transcribed_text"] == "nawiguj do domu"
        and event["source"] == "audio_file"
        for event in runner.logger.events
    )
    assert any(
        event["type"] == "turn_finished"
        and event["audio_path"] == "samples/1.wav"
        and event["reference_text"] == "nawiguj do domu"
        for event in runner.logger.events
    )


def test_runner_stops_turn_when_transcription_returns_none(tmp_path, monkeypatch):
    class FakeAssistant:
        def __init__(self, car):
            self.execution_events = []

        def handle_text(self, text, turn_id=None):
            raise AssertionError("assistant must not run without transcription")

    monkeypatch.setattr("evaluation.conversation_runner.Assistant", FakeAssistant)
    runner = ConversationRunner(CarSystem(), tmp_path, speak_response=lambda _: None)

    result = runner.run_turn(lambda: None, source="microphone")

    assert result is False
    assert runner.logger.events[-1]["type"] == "turn_finished"
    assert runner.logger.events[-1]["status"] == "stopped"


def test_runner_keeps_session_alive_after_agent_failure(tmp_path, monkeypatch):
    class FailingAssistant:
        def __init__(self, car):
            self.execution_events = []

        def handle_text(self, text, turn_id=None):
            raise RuntimeError("agent unavailable")

    monkeypatch.setattr("evaluation.conversation_runner.Assistant", FailingAssistant)
    runner = ConversationRunner(CarSystem(), tmp_path, speak_response=lambda _: None)

    result = runner.run_turn(lambda: "włącz muzykę", source="microphone")

    assert result is True
    assert runner.logger.events[-1]["type"] == "turn_failed"
    assert runner.logger.events[-1]["stage"] == "agent"
