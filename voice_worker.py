"""Background voice loop: ASR → Assistant → TTS, one turn per utterance.

Runs in its own QThread so recognition and LLM calls never block the GUI (WNF-01).
A failed command is reported and the loop keeps listening (WNF-03).

Push-to-talk (microphone mode): the microphone opens only after the GUI talk button,
for one utterance. Pressing again cancels; silence for LISTEN_TIMEOUT_S closes the window.
Without push-to-talk (tests, hands-free) the loop listens continuously.
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
LISTEN_TIMEOUT_S = 8.0   # push-to-talk: give up if no speech starts within this time


class _ListenWindow:
    """Stop condition for one listening window: app shutdown, cancel or timeout."""

    def __init__(self, app_stop):
        self.app_stop = app_stop
        self.cancelled = threading.Event()
        self.heard = threading.Event()   # speech detected; a started utterance is not cut off

    def is_set(self):
        return self.app_stop.is_set() or self.cancelled.is_set()

    def wait(self, timeout=None):
        return self.cancelled.wait(timeout) or self.app_stop.is_set()


class VoiceWorker(QObject):
    finished = Signal()
    userMessage = Signal(str)   # banner text for the GUI; '' hides it
    stateChanged = Signal(str)  # '' idle, 'listening', 'processing'

    def __init__(self, car, report, audio_file: Path | None = None, asr: str | None = None,
                 *, push_to_talk: bool = False):
        super().__init__()
        self.car = car
        self.report = report
        self.audio_file = audio_file   # file mode: exactly one turn, then exit
        self.asr = resolve_model(report.asr_model if asr is None else asr)
        if self.asr != report.asr_model:
            raise ValueError("Model ASR workera musi być zgodny z modelem raportu.")
        self.stop_event = threading.Event()
        self.push_to_talk = push_to_talk and audio_file is None
        self._talk = threading.Event()
        self._window = None

    def stop(self):
        self.stop_event.set()

    def request_talk(self):
        """Talk button (called directly from the GUI thread): open the mic or cancel listening."""
        window = self._window
        if window is not None:
            window.cancelled.set()
        else:
            self._talk.set()

    def _wait_for_talk(self) -> bool:
        while not self.stop_event.is_set():
            if self._talk.wait(0.1):
                self._talk.clear()
                return True
        return False

    def _listen(self, on_event):
        if self.audio_file is not None:
            from asr import listen_file
            return listen_file(self.audio_file, self.stop_event, on_event=on_event, asr=self.asr)
        from asr import listen
        if not self.push_to_talk:
            return listen(self.stop_event, on_event=on_event, asr=self.asr)
        window = _ListenWindow(self.stop_event)

        def observe(event, **data):
            if event == 'speech_detected':
                window.heard.set()
            on_event(event, **data)

        timer = threading.Timer(LISTEN_TIMEOUT_S, lambda: window.heard.is_set() or window.cancelled.set())
        self._window = window
        self.stateChanged.emit('listening')
        timer.start()
        try:
            return listen(window, on_event=observe, asr=self.asr)
        finally:
            timer.cancel()
            self._window = None

    def run(self):
        report = self.report
        turn_id = None
        try:
            assistant = Assistant(self.car)
            while not self.stop_event.is_set():
                self.stateChanged.emit('')
                if self.push_to_talk and not self._wait_for_talk():
                    break
                turn_id = report.begin_turn()
                on_event = partial(report.emit, turn_id=turn_id)
                text = self._listen(on_event)
                if text is None:   # stopped, cancelled or no speech before the timeout
                    report.discard_empty_turn(turn_id)
                    if any(t['id'] == turn_id for t in report.turns):
                        report.end_turn(turn_id, "interrupted")
                    turn_id = None
                    if self.push_to_talk and not self.stop_event.is_set():
                        continue
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
                self.stateChanged.emit('processing')

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
            self.stateChanged.emit('')
            self.finished.emit()

    @staticmethod
    def _speak_response(response: str, on_event=None) -> None:
        from tts import speak, wait_until_speech_done

        speak(response, on_event=on_event)
        wait_until_speech_done()
