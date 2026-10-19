import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject

from evaluation.conversation_runner import ConversationRunner
from tts import speak, wait_until_speech_done


class VoiceWorker(QObject):
    def __init__(self, car):
        super().__init__()
        self.car = car
        self.stop_event = threading.Event()
        self.events: list[dict] = []

    def stop(self):
        self.stop_event.set()

    def run(self):
        from asr import listen

        runner = ConversationRunner(
            self.car,
            Path(__file__).resolve().parent / "evaluation" / "runs",
            speak_response=self._speak_response,
        )
        self.events = runner.logger.events

        while not self.stop_event.is_set():
            completed = runner.run_turn(
                lambda: listen(self.stop_event),
                source="microphone",
            )
            if not completed:
                break

    @staticmethod
    def _speak_response(response: str) -> None:
        speak(response)
        wait_until_speech_done()
        time.sleep(0.7)
