import threading
import time
from uuid import uuid4

from PySide6.QtCore import QObject

from assistant import Assistant
from tts import speak, wait_until_speech_done


class VoiceWorker(QObject):
    def __init__(self, car):
        super().__init__()
        self.car = car
        self.stop_event = threading.Event()
        self.events: list[dict] = []

    def _record_event(self, event_type: str, turn_id: str | None = None, **details):
        self.events.append({
            "type": event_type,
            "turn_id": turn_id,
            "time_ns": time.perf_counter_ns(),
            **details,
        })

    def stop(self):
        self.stop_event.set()

    def run(self):
        from asr import listen

        try:
            assistant = Assistant(self.car)
            assistant.execution_events = self.events

            while not self.stop_event.is_set():
                turn_id = str(uuid4())
                turn_started_at = time.perf_counter_ns()
                self._record_event("turn_started", turn_id)

                asr_started_at = time.perf_counter_ns()
                self._record_event("asr_started", turn_id)
                try:
                    text = listen(self.stop_event)
                except Exception as error:
                    asr_finished_at = time.perf_counter_ns()
                    self._record_event(
                        "asr_failed",
                        turn_id,
                        error_type=type(error).__name__,
                        error_message=str(error),
                        duration_ms=(asr_finished_at - asr_started_at) / 1_000_000,
                    )
                    self._record_event(
                        "turn_failed",
                        turn_id,
                        stage="asr",
                        duration_ms=(asr_finished_at - turn_started_at) / 1_000_000,
                    )
                    break

                asr_finished_at = time.perf_counter_ns()
                self._record_event(
                    "asr_finished",
                    turn_id,
                    transcribed_text=text,
                    duration_ms=(asr_finished_at - asr_started_at) / 1_000_000,
                    status="recognized" if text else "stopped",
                )
                if text is None:
                    self._record_event(
                        "turn_finished",
                        turn_id,
                        success=False,
                        status="stopped",
                        duration_ms=(time.perf_counter_ns() - turn_started_at) / 1_000_000,
                    )
                    break

                print(f"ASR: {text!r}")

                agent_started_at = time.perf_counter_ns()
                self._record_event("agent_started", turn_id)
                try:
                    response = assistant.handle_text(text, turn_id=turn_id)
                    agent_finished_at = time.perf_counter_ns()
                    self._record_event(
                        "agent_finished",
                        turn_id,
                        response=response,
                        duration_ms=(agent_finished_at - agent_started_at) / 1_000_000,
                    )
                    print(response)
                    turn_status = "completed"
                    if response:
                        tts_started_at = time.perf_counter_ns()
                        self._record_event("tts_started", turn_id)
                        try:
                            speak(response)
                            wait_until_speech_done()
                            tts_finished_at = time.perf_counter_ns()
                            self._record_event(
                                "tts_finished",
                                turn_id,
                                success=True,
                                duration_ms=(tts_finished_at - tts_started_at) / 1_000_000,
                            )
                            time.sleep(0.7)
                        except Exception as error:
                            tts_finished_at = time.perf_counter_ns()
                            self._record_event(
                                "tts_failed",
                                turn_id,
                                error_type=type(error).__name__,
                                error_message=str(error),
                                duration_ms=(tts_finished_at - tts_started_at) / 1_000_000,
                            )
                            turn_status = "completed_with_tts_error"
                    self._record_event(
                        "turn_finished",
                        turn_id,
                        status=turn_status,
                        transcribed_text=text,
                        duration_ms=(time.perf_counter_ns() - turn_started_at) / 1_000_000,
                    )
                except Exception as error:
                    self._record_event(
                        "agent_failed",
                        turn_id,
                        error_type=type(error).__name__,
                        error_message=str(error),
                        duration_ms=(time.perf_counter_ns() - agent_started_at) / 1_000_000,
                    )
                    self._record_event(
                        "turn_failed",
                        turn_id,
                        stage="agent",
                        transcribed_text=text,
                        duration_ms=(time.perf_counter_ns() - turn_started_at) / 1_000_000,
                    )
                    print(f"Voice assistant error: {error}")
        except Exception as error:
            self._record_event(
                "worker_failed",
                error_type=type(error).__name__,
                error_message=str(error),
            )
            print(f"Voice worker stopped: {error}")
