"""Closing the app: stop the voice loop, record the final HMI state, save the session report."""

from pathlib import Path

from PySide6.QtCore import QObject, Property, Signal, Slot


class ShutdownController(QObject):
    closingChanged = Signal()
    finished = Signal()

    def __init__(self, stop_event, report, report_directory=Path("logs/sessions"), *, car=None):
        super().__init__()
        self.stop_event = stop_event
        self.report = report
        self.report_directory = Path(report_directory)
        self.car = car
        self._closing = False

    @Property(bool, notify=closingChanged)
    def closing(self):
        return self._closing

    @Slot()
    def request_shutdown(self):
        if self._closing:
            return
        self._closing = True
        # The event can be set from the GUI even while the assistant thread is busy.
        self.stop_event.set()
        self.closingChanged.emit()

    @Slot()
    def finish(self):
        if self.car is not None:
            try:
                self.report.emit('app_state', state=self._app_state())
            except Exception as error:
                print(f"Nie udało się odczytać stanu końcowego: {error}", flush=True)
        try:
            for path in self.report.save(self.report_directory):
                print(f"Raport: {path.resolve()}", flush=True)
        except Exception as error:
            print(f"Nie udało się zapisać raportu: {error}", flush=True)
        finally:
            self.finished.emit()

    def _app_state(self):
        """Final state compared by the runner with the expected effect of the task."""
        music, contacts, navigation = self.car.music, self.car.contacts, self.car.navigation
        return {
            'music': {'title': music.tracks[music.currentTrackIndex]['title'], 'is_playing': music.isPlaying},
            'contacts': {'name': contacts.currentContactName, 'is_calling': contacts.isCalling},
            'navigation': {'destination': navigation.destination, 'stops': navigation.stops},
        }
