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
