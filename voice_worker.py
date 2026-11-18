"""Background voice loop: ASR → Assistant → TTS, one turn per utterance.

Runs in its own QThread so recognition and LLM calls never block the GUI (WNF-01).
A failed command is reported and the loop keeps listening (WNF-03).
"""

import re
import sys
import threading
import time
from functools import partial
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from langgraph.errors import GraphRecursionError

from asr import resolve_model
from assistant import Assistant, IncompleteExecutionError

FAILED_COMMAND_MESSAGE = 'Nie ukończono polecenia. Sprawdź stan wykonanych czynności.'


class VoiceWorker(QObject):
    finished = Signal()
    userMessage = Signal(str)   # banner text for the GUI; '' hides it

    def __init__(self, car, report, audio_file: Path | None = None, asr: str | None = None):
        super().__init__()
        self.car = car
        self.report = report
        self.audio_file = audio_file   # file mode: exactly one turn, then exit
        self.asr = resolve_model(report.asr_model if asr is None else asr)
        if self.asr != report.asr_model:
            raise ValueError("Model ASR workera musi być zgodny z modelem raportu.")
        self.stop_event = threading.Event()

    def stop(self):
        self.stop_event.set()

    def run(self):
        report = self.report
        turn_id = None
        try:
            from asr import listen, listen_file

            assistant = Assistant(self.car)
            while not self.stop_event.is_set():
                turn_id = report.begin_turn()
                on_event = partial(report.emit, turn_id=turn_id)
                if self.audio_file is not None:
                    text = listen_file(self.audio_file, self.stop_event, on_event=on_event, asr=self.asr)
                else:
                    text = listen(self.stop_event, on_event=on_event, asr=self.asr)
                if text is None:   # stopped while listening
                    report.discard_empty_turn(turn_id)
                    if any(t['id'] == turn_id for t in report.turns):
                        report.end_turn(turn_id, "interrupted")
                    break

                # Whisper marks non-speech as [music], [laughter] etc.; never send it to the LLM.
                spoken_text = re.sub(r'\[[^\[\]]*\]', '', text).strip()
                if not re.search(r'\w', spoken_text):
                    report.emit('asr_warning', turn_id=turn_id,
                                warning='Pominięto wejście bez rozpoznanej mowy.', text=text)
                    report.end_turn(turn_id, 'interrupted')
                    turn_id = None
                    if self.audio_file is not None:
                        break
                    continue
                self.userMessage.emit('')

                try:
                    response = assistant.handle_text(spoken_text, report=report, turn_id=turn_id)
                except (IncompleteExecutionError, GraphRecursionError) as error:
                    if self.audio_file is not None:
                        raise
                    report.emit("session_error", turn_id=turn_id, error=str(error))
                    report.end_turn(turn_id, "failed")
                    print(f"Nie ukończono polecenia: {error}. Słucham dalej.", file=sys.stderr, flush=True)
                    self.userMessage.emit(FAILED_COMMAND_MESSAGE)
                    turn_id = None
                    continue
                if response:
                    self._speak_response(response, on_event=on_event)
                report.end_turn(turn_id, "completed")
                turn_id = None
                if self.audio_file is not None:
                    break
                if response:
                    time.sleep(0.7)   # let the speaker's echo fade before listening again
        except Exception as error:
            report.emit("session_error", turn_id=turn_id, error=str(error))
            if turn_id is not None:
                report.end_turn(turn_id, "failed")
            if isinstance(error, ConnectionError):
                print(str(error), file=sys.stderr, flush=True)
            else:
                raise
        finally:
            self.finished.emit()

    @staticmethod
    def _speak_response(response: str, on_event=None) -> None:
        from tts import speak, wait_until_speech_done

        speak(response, on_event=on_event)
        wait_until_speech_done()
