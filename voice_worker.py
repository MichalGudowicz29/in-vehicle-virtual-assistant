import threading
import time

from PySide6.QtCore import QObject, Signal

from assistant import Assistant


class VoiceWorker(QObject):
    finished = Signal()

    def __init__(self, car):
        super().__init__()
        self.car = car
        self.stop_event = threading.Event()

    def stop(self):
        self.stop_event.set()

    def run(self):
        try:
            from asr import listen

            assistant = Assistant(self.car)

            while not self.stop_event.is_set():
                text = listen(self.stop_event)
                if text is None:
                    break

                response = assistant.handle_text(text)
                if response:
                    self._speak_response(response)
        finally:
            self.finished.emit()

    @staticmethod
    def _speak_response(response: str) -> None:
        from tts import speak, wait_until_speech_done

        speak(response)
        wait_until_speech_done()
        time.sleep(0.7)
