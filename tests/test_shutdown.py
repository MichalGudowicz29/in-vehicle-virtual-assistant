from pathlib import Path
from threading import Event

from shutdown import ShutdownController


def test_shutdown_requests_stop_once_and_saves_report(tmp_path):
    from session_report import SessionReport
    stop = Event()
    controller = ShutdownController(stop, SessionReport(), report_directory=tmp_path)
    notifications = []
    controller.closingChanged.connect(lambda: notifications.append(True))

    controller.request_shutdown()
    controller.request_shutdown()

    assert stop.is_set()
    assert controller.closing
    assert notifications == [True]

    controller.finish()
    assert len(list(tmp_path.glob("session_*.json"))) == 1


def test_shutdown_saves_detailed_session_report(monkeypatch, tmp_path):
    import json
    from session_report import SessionReport
    monkeypatch.chdir(tmp_path)
    report = SessionReport()
    turn = report.begin_turn()
    report.emit('transcription_ready', turn_id=turn, text='Włącz muzykę')
    report.end_turn(turn, 'failed')
    controller = ShutdownController(Event(), report=report)
    controller.finish()
    paths = list(Path('logs/sessions').glob('*.json'))
    assert len(paths) == 1
    assert json.loads(paths[0].read_text())['counts']['failed'] == 1
    assert 'Włącz muzykę' in paths[0].with_suffix('.txt').read_text()


def test_report_save_error_does_not_block_shutdown(monkeypatch, tmp_path):
    from session_report import SessionReport
    report = SessionReport()
    def fail(*args):
        raise OSError('disk full')
    monkeypatch.setattr(report, 'save', fail)
    controller = ShutdownController(Event(), report=report)
    finished = []
    controller.finished.connect(lambda: finished.append(True))
    controller.finish()
    assert finished == [True]


def test_shutdown_saves_actual_final_application_state(tmp_path):
    import json
    from CarSystem.car_system import CarSystem
    from session_report import SessionReport
    car = CarSystem()
    car.music.select_track('Christmas Eve')
    car.contacts.call_contact('Robert Lewandowski', 'mobile')
    car.navigation.set_destination('ul. Żołnierska 47, Szczecin')
    report = SessionReport()
    controller = ShutdownController(Event(), report=report, report_directory=tmp_path, car=car)
    controller.finish()
    path, = tmp_path.glob('*.json')
    data = json.loads(path.read_text())
    event, = [event for event in data['events'] if event['type'] == 'app_state']
    assert event['state'] == {
        'music': {'title': 'Christmas Eve', 'is_playing': True},
        'contacts': {'name': 'Robert Lewandowski', 'is_calling': True},
        'navigation': {'destination': 'ul. Żołnierska 47, Szczecin', 'stops': []},
    }
    assert 'Stan końcowy aplikacji' in path.with_suffix('.txt').read_text()


def test_final_state_capture_failure_does_not_lose_session_report(tmp_path):
    from types import SimpleNamespace
    from session_report import SessionReport
    report = SessionReport()
    report.emit('session_error', error='original error')
    controller = ShutdownController(Event(), report=report, report_directory=tmp_path,
                                    car=SimpleNamespace(music=None))
    controller.finish()
    path, = tmp_path.glob('*.json')
    assert 'original error' in path.read_text()


def test_custom_report_directory_keeps_ten_runs_separate(monkeypatch, tmp_path):
    import json
    from session_report import SessionReport
    monkeypatch.chdir(tmp_path)
    output = tmp_path / 'Konfiguracja1_Zadanie1' / 'raporty sesji'
    session_ids = set()
    for _ in range(10):
        report = SessionReport()
        turn = report.begin_turn()
        report.end_turn(turn, 'completed')
        controller = ShutdownController(Event(), report=report, report_directory=output)
        controller.finish()
        session_ids.add(report.session_id)
    paths = list(output.glob('*.json'))
    assert len(paths) == 10
    assert len(list(output.glob('*.txt'))) == 10
    assert {json.loads(path.read_text())['session_id'] for path in paths} == session_ids
    assert not Path('logs/sessions').exists()
