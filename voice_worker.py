import threading

from PySide6.QtCore import QObject

from assistant import Assistant
from tts import speak, wait_until_speech_done


class VoiceWorker(QObject):
    def __init__(self, car):
        super().__init__()
        self.car = car
        self.stop_event = threading.Event()

    def stop(self):
        self.stop_event.set()

    def run(self):
        from asr import listen

        try:
            assistant = Assistant(self.car)

            while not self.stop_event.is_set():
                text = listen(self.stop_event)
                if text is None:
                    break

                try:
                    response = assistant.handle_text(text)
                    print(response)
                    if response:
                        speak(response)
                        wait_until_speech_done()
                except Exception as error:
                    print(f"Voice assistant error: {error}")
        except Exception as error:
            print(f"Voice worker stopped: {error}")
