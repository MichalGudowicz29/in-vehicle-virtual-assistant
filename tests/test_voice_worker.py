from session_report import SessionReport
from CarSystem.car_system import CarSystem
from voice_worker import VoiceWorker
import pytest
from assistant import IncompleteExecutionError
from langgraph.errors import GraphRecursionError


@pytest.mark.parametrize('error_type, message', [
    (IncompleteExecutionError, 'Model zwrócił pusty plan'),
    (GraphRecursionError, 'Recursion limit of 24 reached'),
])
def test_incomplete_manual_turn_is_failed_and_next_turn_still_completes(monkeypatch, capsys, tmp_path, error_type, message):
    import json
    from assistant import IncompleteExecutionError
    from session_report import SessionReport

    report = SessionReport()
    texts = iter(['pierwsza komenda', 'druga komenda', None])
    actions = []
    def listen(stop, on_event, **kwargs):
        text = next(texts)
        if text:
            on_event('transcription_ready', text=text)
        return text
    class FakeAssistant:
        def __init__(self, car):
            pass
        def handle_text(self, text, *, report, turn_id):
            assert 'finished' not in actions
            actions.append(text)
            if turn_id == 1:
                raise error_type(message)
            return 'Gotowe'
    monkeypatch.setattr('asr.listen', listen)
    monkeypatch.setattr('voice_worker.Assistant', FakeAssistant)
    monkeypatch.setattr('voice_worker.time.sleep', lambda _: None)
    worker = VoiceWorker(None, report=report)
    messages = []
    worker.userMessage.connect(messages.append)
    monkeypatch.setattr(worker, '_speak_response', lambda text, **kwargs: actions.append(text))
    worker.finished.connect(lambda: actions.append('finished'))

    worker.run()

    assert actions == ['pierwsza komenda', 'druga komenda', 'Gotowe', 'finished']
    assert messages == ['', 'Nie ukończono polecenia. Sprawdź stan wykonanych czynności.', '']
    printed = capsys.readouterr().err
    assert message in printed
    assert 'Słucham dalej' in printed
    report.save(tmp_path)
    data = json.loads(next(tmp_path.glob('*.json')).read_text())
    assert data['counts'] == {'completed': 1, 'failed': 1, 'interrupted': 0}
    assert [turn['status'] for turn in data['turns']] == ['failed', 'completed']
    errors = [event for event in data['events'] if event['type'] == 'session_error']
    assert len(errors) == 1
    assert errors[0]['turn_id'] == 1
    assert errors[0]['error'] == message


@pytest.mark.parametrize('error_type', [IncompleteExecutionError, GraphRecursionError])
def test_incomplete_file_turn_propagates_and_records_failure(monkeypatch, tmp_path, error_type):
    import pytest
    from assistant import IncompleteExecutionError
    from session_report import SessionReport

    path = tmp_path / 'speech.wav'
    report = SessionReport(audio_file=path)
    class FakeAssistant:
        def __init__(self, car):
            pass
        def handle_text(self, text, **kwargs):
            raise error_type('Model zwrócił pusty plan')
    monkeypatch.setattr('voice_worker.Assistant', FakeAssistant)
    monkeypatch.setattr('asr.listen_file', lambda *args, **kwargs: 'test')
    worker = VoiceWorker(None, report=report, audio_file=path)
    finished = []
    worker.finished.connect(lambda: finished.append(True))

    with pytest.raises(error_type, match='pusty plan'):
        worker.run()

    assert finished == [True]
    assert report.snapshot()['counts']['failed'] == 1


@pytest.mark.parametrize('annotation', ['[oklaski]', ' [muzyka] [brawa] ', '♪ ... ♫'])
def test_non_speech_is_recorded_without_calling_agent_and_listening_continues(monkeypatch, annotation):
    from session_report import SessionReport

    report = SessionReport()
    texts = iter([annotation, 'Zadzwoń do Roberta', None])
    received = []

    def listen(stop, on_event, **kwargs):
        text = next(texts)
        if text is not None:
            on_event('transcription_ready', text=text)
        return text

    class Agent:
        def __init__(self, car):
            pass

        def handle_text(self, text, **kwargs):
            received.append(text)
            return ''

    monkeypatch.setattr('asr.listen', listen)
    monkeypatch.setattr('voice_worker.Assistant', Agent)
    worker = VoiceWorker(None, report=report)
    worker.run()
    assert received == ['Zadzwoń do Roberta']
    data = report.snapshot()
    assert data['counts'] == {'completed': 1, 'failed': 0, 'interrupted': 1}
    assert any(event['type'] == 'asr_warning' and event['turn_id'] == 1 for event in data['events'])
    assert any(event.get('text') == annotation for event in data['events'])


@pytest.mark.parametrize('text, expected', [
    (' [muzyka] Włącz Christmas Eve ', 'Włącz Christmas Eve'),
    ('Włącz Christmas Eve (live)', 'Włącz Christmas Eve (live)'),
])
def test_annotation_filter_preserves_spoken_command(monkeypatch, text, expected):
    received = []

    class Agent:
        def __init__(self, car):
            pass

        def handle_text(self, text, **kwargs):
            received.append(text)
            worker.stop()
            return ''

    monkeypatch.setattr('asr.listen', lambda *args, **kwargs: text)
    monkeypatch.setattr('voice_worker.Assistant', Agent)
    worker = VoiceWorker(None, SessionReport())
    worker.run()
    assert received == [expected]


def test_voice_worker_sends_microphone_transcription_to_assistant(monkeypatch):
    received = {}

    class FakeAssistant:
        def __init__(self, car):
            pass

        def handle_text(self, text, **kwargs):
            received["text"] = text
            worker.stop_event.set()
            return ""

    monkeypatch.setattr("voice_worker.Assistant", FakeAssistant)
    monkeypatch.setattr("asr.listen", lambda stop_event, **kwargs: "włącz muzykę")
    worker = VoiceWorker(CarSystem(), SessionReport())

    worker.run()

    assert received == {"text": "włącz muzykę"}


def test_stop_finishes_response_before_signalling_finished(monkeypatch):
    actions = []

    class FakeAssistant:
        def __init__(self, car):
            pass

        def handle_text(self, text, **kwargs):
            worker.stop()
            return "Gotowe"

    monkeypatch.setattr("voice_worker.Assistant", FakeAssistant)
    monkeypatch.setattr("asr.listen", lambda stop_event, **kwargs: "włącz muzykę")
    worker = VoiceWorker(None, SessionReport())
    monkeypatch.setattr(worker, "_speak_response", lambda text, **kwargs: actions.append(text))
    worker.finished.connect(lambda: actions.append("finished"))

    worker.run()

    assert actions == ["Gotowe", "finished"]


def test_finished_is_emitted_also_when_assistant_fails(monkeypatch):
    import pytest

    def fail(car):
        raise RuntimeError("Cannot initialize assistant")

    monkeypatch.setattr("voice_worker.Assistant", fail)
    worker = VoiceWorker(None, SessionReport())
    finished = []
    worker.finished.connect(lambda: finished.append(True))

    with pytest.raises(RuntimeError):
        worker.run()

    assert finished == [True]


def test_reported_turn_finishes_after_audio_and_empty_listening_is_discarded(monkeypatch):
    from session_report import SessionReport
    report = SessionReport()
    texts = iter(['włącz muzykę', None])
    def listen(stop, on_event, **kwargs):
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
    def listen(stop, on_event, **kwargs):
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


def test_file_input_runs_exactly_one_turn_without_opening_microphone(monkeypatch, tmp_path):
    from session_report import SessionReport
    path = tmp_path / 'speech.mp3'
    report = SessionReport(audio_file=path)
    calls = []
    class FakeAssistant:
        def __init__(self, car):
            pass
        def handle_text(self, text, *, report, turn_id):
            calls.append(('agent', text))
            report.emit('agent_start', turn_id=turn_id)
            report.emit('agent_end', turn_id=turn_id, text='Gotowe')
            return 'Gotowe'
    def read_file(audio_file, stop, on_event, **kwargs):
        assert not calls, 'File must not be read a second time'
        assert audio_file == path
        calls.append(('file', audio_file))
        on_event('speech_start')
        on_event('speech_end')
        on_event('transcription_ready', text='zadzwoń do Roberta')
        return 'zadzwoń do Roberta'
    def unexpected_microphone(*args, **kwargs):
        raise AssertionError('File mode must never open the microphone')
    monkeypatch.setattr('asr.listen', unexpected_microphone)
    monkeypatch.setattr('asr.listen_file', read_file)
    monkeypatch.setattr('voice_worker.Assistant', FakeAssistant)
    worker = VoiceWorker(None, report=report, audio_file=path)
    def speak(text, on_event):
        calls.append(('tts', text))
        on_event('audio_start')
        on_event('audio_end')
    monkeypatch.setattr(worker, '_speak_response', speak)
    worker.finished.connect(lambda: calls.append(('finished', None)))
    worker.run()
    assert [kind for kind, _ in calls] == ['file', 'agent', 'tts', 'finished']
    data = report.snapshot()
    assert data['counts'] == {'completed': 1, 'failed': 0, 'interrupted': 0}
    assert [e['type'] for e in data['events']][-2:] == ['audio_end', 'turn_end']


def test_invalid_audio_file_is_a_failed_turn_and_worker_still_finishes(monkeypatch, tmp_path):
    import pytest
    from session_report import SessionReport
    class FakeAssistant:
        def __init__(self, car):
            pass
        def handle_text(self, text, **kwargs):
            raise AssertionError('Invalid audio must not reach the agent')
    monkeypatch.setattr('voice_worker.Assistant', FakeAssistant)
    path = tmp_path / 'broken.mp3'
    path.write_text('not audio')
    report = SessionReport(audio_file=path)
    worker = VoiceWorker(None, report=report, audio_file=path)
    finished = []
    worker.finished.connect(lambda: finished.append(True))
    with pytest.raises((RuntimeError, OSError)):
        worker.run()
    assert finished == [True]
    assert report.snapshot()['counts']['failed'] == 1


def test_unavailable_ollama_prints_actionable_message_and_records_failed_turn(monkeypatch, capsys):
    import httpx
    from langchain_ollama import ChatOllama
    from session_report import SessionReport

    requests = []
    def refused(request):
        requests.append(str(request.url))
        raise httpx.ConnectError('[Errno 61] Connection refused', request=request)
    def local_model(**kwargs):
        return ChatOllama(**{**kwargs, 'client_kwargs': {
            **kwargs['client_kwargs'], 'transport': httpx.MockTransport(refused),
        }})
    monkeypatch.setattr('assistant.agent.ChatOllama', local_model)
    monkeypatch.setattr('asr.listen', lambda stop, **kwargs: 'Włącz muzykę')
    report = SessionReport()
    worker = VoiceWorker(CarSystem(), report=report)
    finished = []
    worker.finished.connect(lambda: finished.append(True))
    worker.run()
    message = capsys.readouterr().err
    assert 'Nie można połączyć się z Ollamą' in message
    assert 'http://127.0.0.1:11434' in message
    assert 'ollama serve' in message
    assert 'Traceback' not in message
    assert requests == ['http://127.0.0.1:11434/api/chat']
    assert finished == [True]
    data = report.snapshot()
    assert data['counts']['failed'] == 1
    error = next(e for e in data['events'] if e['type'] == 'session_error')
    assert error['error'] == message.strip()


def test_silent_completion_records_turn_without_invoking_tts(monkeypatch, tmp_path):
    from session_report import SessionReport
    path = tmp_path / 'Telefon.mp3'
    report = SessionReport(audio_file=path)
    class Assistant:
        def __init__(self, car):
            pass
        def handle_text(self, text, *, report, turn_id):
            report.emit('agent_start', turn_id=turn_id)
            report.emit('agent_end', turn_id=turn_id, success=True, text='')
            return ''
    def listen_file(path, stop, *, on_event, **kwargs):
        on_event('speech_start')
        on_event('speech_end')
        on_event('transcription_ready', text='Zadzwoń do Roberta Lewandowskiego')
        return 'Zadzwoń do Roberta Lewandowskiego'
    def unexpected_speech(*args, **kwargs):
        raise AssertionError('Silent completion must not synthesize or play audio')
    monkeypatch.setattr('voice_worker.Assistant', Assistant)
    monkeypatch.setattr('asr.listen_file', listen_file)
    worker = VoiceWorker(None, report=report, audio_file=path)
    monkeypatch.setattr(worker, '_speak_response', unexpected_speech)
    worker.run()
    data = report.snapshot()
    assert data['counts']['completed'] == 1
    assert data['events'][-1]['type'] == 'turn_end'
    assert next(e for e in data['events'] if e['type'] == 'agent_end')['text'] == ''
    assert 'Synteza TTS' not in data['metrics']
    assert 'Odtwarzanie' not in data['metrics']


def test_push_to_talk_listens_only_after_button_and_survives_silence(monkeypatch):
    import threading
    import voice_worker as module

    listens, states, handled = [], [], []

    class FakeAssistant:
        def __init__(self, car):
            pass

        def handle_text(self, text, **kwargs):
            handled.append(text)
            worker.stop()
            return ''

    def listen(stop, **kwargs):
        listens.append(stop)
        if len(listens) == 1:
            return None              # no speech before the timeout: back to idle
        kwargs['on_event']('speech_detected')
        return 'zadzwoń do Roberta'

    monkeypatch.setattr('voice_worker.Assistant', FakeAssistant)
    monkeypatch.setattr('asr.listen', listen)
    worker = VoiceWorker(None, SessionReport(), push_to_talk=True)
    from PySide6.QtCore import Qt
    worker.stateChanged.connect(states.append, Qt.ConnectionType.DirectConnection)
    thread = threading.Thread(target=worker.run)
    thread.start()
    threading.Event().wait(0.3)
    assert listens == []             # microphone stays closed until the button
    worker.request_talk()
    threading.Event().wait(0.3)
    assert len(listens) == 1 and thread.is_alive()
    worker.request_talk()
    thread.join(timeout=3)
    assert handled == ['zadzwoń do Roberta']
    assert isinstance(listens[0], module._ListenWindow)
    assert states.count('listening') == 2 and 'processing' in states and states[-1] == ''


def test_second_press_cancels_listening_window():
    import voice_worker as module

    worker = VoiceWorker(None, SessionReport(), push_to_talk=True)
    window = module._ListenWindow(worker.stop_event)
    worker._window = window
    worker.request_talk()
    assert window.is_set() and not worker._talk.is_set()
    worker._window = None
    worker.request_talk()
    assert worker._talk.is_set()


def test_listen_timeout_closes_window_only_without_speech(monkeypatch):
    import voice_worker as module

    monkeypatch.setattr(module, 'LISTEN_TIMEOUT_S', 0.05)
    worker = VoiceWorker(None, SessionReport(), push_to_talk=True)
    seen = {}

    def listen(window, on_event, **kwargs):
        threading_wait = __import__('threading').Event().wait
        threading_wait(0.2)
        seen['silent'] = window.is_set()
        return None

    monkeypatch.setattr('asr.listen', listen)
    worker._listen(lambda *a, **k: None)
    assert seen['silent'] is True

    def listen_speaking(window, on_event, **kwargs):
        on_event('speech_detected')
        __import__('threading').Event().wait(0.2)
        seen['speaking'] = window.is_set()
        return 'tekst'

    monkeypatch.setattr('asr.listen', listen_speaking)
    assert worker._listen(lambda *a, **k: None) == 'tekst'
    assert seen['speaking'] is False
