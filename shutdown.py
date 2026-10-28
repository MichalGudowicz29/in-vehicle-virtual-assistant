from datetime import datetime
from pathlib import Path
from time import perf_counter

from PySide6.QtCore import QObject, Property, Signal, Slot


class ShutdownController(QObject):
    closingChanged = Signal()
    finished = Signal()

    def __init__(self, stop_event, report=None):
        super().__init__()
        self.stop_event = stop_event
        self.report = report
        self._closing = False
        self.started_at = datetime.now().astimezone()
        self.started_timer = perf_counter()

    @Property(bool, notify=closingChanged)
    def closing(self):
        return self._closing

    @Slot()
    def request_shutdown(self):
        if self._closing:
            return
        self._closing = True
        # Event można ustawić z UI, nawet gdy wątek asystenta jest zajęty.
        self.stop_event.set()
        self.closingChanged.emit()

    @Slot()
    def finish(self):
        if self.report is not None:
            try:
                for path in self.report.save():
                    print(f"Raport: {path.resolve()}", flush=True)
            except Exception as error:
                print(f"Nie udało się zapisać raportu: {error}", flush=True)
            finally:
                self.finished.emit()
            return
        ended_at = datetime.now().astimezone()
        duration = perf_counter() - self.started_timer
        report = (
            f"Rozpoczęcie: {self.started_at.isoformat(timespec='seconds')}\n"
            f"Zakończenie: {ended_at.isoformat(timespec='seconds')}\n"
            f"Czas sesji: {duration:.3f} s\n"
        )
        print(report, flush=True)
        try:
            directory = Path("logs/sessions")
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / f"{self.started_at:%Y%m%d_%H%M%S_%f}.txt"
            path.write_text(report, encoding="utf-8")
            print(f"Raport: {path.resolve()}", flush=True)
        except OSError as error:
            print(f"Nie udało się zapisać raportu: {error}", flush=True)
        finally:
            self.finished.emit()
