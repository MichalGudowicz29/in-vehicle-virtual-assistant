from PySide6.QtCore import QObject
from assistant import Assistant
from tts import speak, wait_until_speech_done


class VoiceWorker(QObject):
    def __init__(self, car):
        super().__init__()
        self.car = car

    def run(self):
        from asr import listen

        assistant = Assistant(self.car)

        while True:
            text = listen()

            if text is None:
                break

            if text:
                response = assistant.handle_text(text)
                print(response)

                speak(response)
                wait_until_speech_done()