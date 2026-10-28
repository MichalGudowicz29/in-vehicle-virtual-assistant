from pathlib import Path
from threading import Event

from shutdown import ShutdownController


def test_shutdown_requests_stop_once_and_writes_session_times(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    stop = Event()
    controller = ShutdownController(stop)
    notifications = []
    controller.closingChanged.connect(lambda: notifications.append(True))

    controller.request_shutdown()
    controller.request_shutdown()

    assert stop.is_set()
    assert controller.closing
    assert notifications == [True]

    controller.finish()
    reports = list(Path("logs/sessions").glob("*.txt"))
    assert len(reports) == 1
    text = reports[0].read_text()
    assert "Rozpoczęcie:" in text
    assert "Zakończenie:" in text
    assert "Czas sesji:" in text


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
