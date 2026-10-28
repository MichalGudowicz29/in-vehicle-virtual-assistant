import threading
import time
from functools import partial

from PySide6.QtCore import QObject, Signal

from assistant import Assistant


class VoiceWorker(QObject):
    finished = Signal()

    def __init__(self, car, report=None):
        super().__init__()
        self.car = car
        self.report = report
        self.stop_event = threading.Event()

    def stop(self):
        self.stop_event.set()

    def run(self):
        turn_id = None
        try:
            from asr import listen

            assistant = Assistant(self.car)

            while not self.stop_event.is_set():
                if self.report is not None:
                    turn_id = self.report.begin_turn()
                    on_event = partial(self.report.emit, turn_id=turn_id)
                    text = listen(self.stop_event, on_event=on_event)
                else:
                    text = listen(self.stop_event)
                if text is None:
                    if self.report is not None:
                        self.report.discard_empty_turn(turn_id)
                        if any(t['id'] == turn_id for t in self.report.turns):
                            self.report.end_turn(turn_id, "interrupted")
                    break

                if self.report is not None:
                    response = assistant.handle_text(text, report=self.report, turn_id=turn_id)
                else:
                    response = assistant.handle_text(text)
                if response:
                    if self.report is not None:
                        self._speak_response(response, on_event=on_event)
                    else:
                        self._speak_response(response)
                if self.report is not None:
                    self.report.end_turn(turn_id, "completed")
                turn_id = None
                if response:
                    time.sleep(0.7)
        except Exception as error:
            if self.report is not None:
                self.report.emit("session_error", turn_id=turn_id, error=str(error))
                if turn_id is not None:
                    self.report.end_turn(turn_id, "failed")
            raise
        finally:
            self.finished.emit()

    @staticmethod
    def _speak_response(response: str, on_event=None) -> None:
        from tts import speak, wait_until_speech_done

        speak(response, on_event=on_event)
        wait_until_speech_done()
