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


def test_reported_turn_finishes_after_audio_and_empty_listening_is_discarded(monkeypatch):
    from session_report import SessionReport
    report = SessionReport()
    texts = iter(['włącz muzykę', None])
    def listen(stop, on_event):
        text = next(texts)
        if text:
            on_event('transcription_ready', text=text)
        return text
    class FakeAssistant:
        def __init__(self, car):
            pass
        def handle_text(self, text, *, report, turn_id):
            report.emit('agent_start', turn_id=turn_id)
            report.emit('agent_end', turn_id=turn_id, text='Gotowe')
            return 'Gotowe'
    monkeypatch.setattr('asr.listen', listen)
    monkeypatch.setattr('voice_worker.Assistant', FakeAssistant)
    worker = VoiceWorker(None, report=report)
    def speak(text, on_event):
        on_event('audio_start')
        on_event('audio_end')
    monkeypatch.setattr(worker, '_speak_response', speak)
    worker.run()
    data = report.snapshot()
    assert data['counts']['completed'] == 1
    assert len(data['turns']) == 1
    assert [e['type'] for e in data['events']][-2:] == ['audio_end', 'turn_end']


def test_report_records_agent_failure_before_worker_finishes(monkeypatch):
    import pytest
    from session_report import SessionReport
    report = SessionReport()
    class FakeAssistant:
        def __init__(self, car):
            pass
        def handle_text(self, text, **kwargs):
            raise RuntimeError('offline')
    monkeypatch.setattr('asr.listen', lambda stop, **kwargs: 'test')
    monkeypatch.setattr('voice_worker.Assistant', FakeAssistant)
    worker = VoiceWorker(None, report=report)
    with pytest.raises(RuntimeError, match='offline'):
        worker.run()
    assert report.snapshot()['counts']['failed'] == 1


def test_post_response_pause_is_excluded_from_turn_duration(monkeypatch):
    import sys
    from types import SimpleNamespace
    from session_report import SessionReport
    clock = [100.0]
    monkeypatch.setattr('session_report.perf_counter', lambda: clock[0])
    report = SessionReport()
    class FakeAssistant:
        def __init__(self, car):
            pass
        def handle_text(self, text, **kwargs):
            return 'Gotowe'
    def listen(stop, on_event):
        on_event('speech_start')
        clock[0] += 1
        on_event('speech_end')
        on_event('transcription_ready', text='test')
        return 'test'
    def speak(text, on_event):
        on_event('audio_start')
        clock[0] += 2
        on_event('audio_end')
        worker.stop()
    monkeypatch.setattr('voice_worker.Assistant', FakeAssistant)
    monkeypatch.setattr('asr.listen', listen)
    monkeypatch.setitem(sys.modules, 'tts', SimpleNamespace(speak=speak, wait_until_speech_done=lambda: None))
    monkeypatch.setattr('voice_worker.time.sleep', lambda duration: clock.__setitem__(0, clock[0] + duration))
    worker = VoiceWorker(None, report=report)
    worker.run()
    assert report.snapshot()['metrics']['Cała tura']['mean_s'] == 3
    assert report.snapshot()['duration_s'] > 3
