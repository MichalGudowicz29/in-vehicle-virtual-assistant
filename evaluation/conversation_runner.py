import time
from pathlib import Path
from typing import Callable
from uuid import uuid4

from assistant import Assistant
from evaluation.event_logger import EventLogger


class ConversationRunner:
    def __init__(
        self,
        car,
        output_dir: Path,
        speak_response: Callable[[str], None],
    ):
        self.logger = EventLogger(output_dir)
        self.assistant = Assistant(car)
        self.assistant.execution_events = self.logger
        self.speak_response = speak_response

    def run_turn(
        self,
        transcribe: Callable[[], str | None],
        source: str,
        reference_text: str | None = None,
        audio_path: str | None = None,
    ) -> bool:
        turn_id = str(uuid4())
        turn_started_at = time.perf_counter_ns()
        metadata = {"source": source}
        if reference_text is not None:
            metadata["reference_text"] = reference_text
        if audio_path is not None:
            metadata["audio_path"] = audio_path

        self._record("turn_started", turn_id, **metadata)
        asr_started_at = time.perf_counter_ns()
        self._record("asr_started", turn_id, **metadata)
        try:
            text = transcribe()
        except Exception as error:
            self._record(
                "asr_failed",
                turn_id,
                **metadata,
                error_type=type(error).__name__,
                error_message=str(error),
                duration_ms=self._duration_ms(asr_started_at),
            )
            self._record(
                "turn_failed",
                turn_id,
                **metadata,
                stage="asr",
                duration_ms=self._duration_ms(turn_started_at),
            )
            return False

        self._record(
            "asr_finished",
            turn_id,
            **metadata,
            transcribed_text=text,
            status="recognized" if text is not None else "stopped",
            duration_ms=self._duration_ms(asr_started_at),
        )
        if text is None:
            self._record(
                "turn_finished",
                turn_id,
                **metadata,
                transcribed_text=None,
                status="stopped",
                success=False,
                duration_ms=self._duration_ms(turn_started_at),
            )
            return False

        agent_started_at = time.perf_counter_ns()
        self._record("agent_started", turn_id, **metadata)
        try:
            response = self.assistant.handle_text(text, turn_id=turn_id)
        except Exception as error:
            self._record(
                "agent_failed",
                turn_id,
                **metadata,
                transcribed_text=text,
                error_type=type(error).__name__,
                error_message=str(error),
                duration_ms=self._duration_ms(agent_started_at),
            )
            self._record(
                "turn_failed",
                turn_id,
                **metadata,
                transcribed_text=text,
                stage="agent",
                duration_ms=self._duration_ms(turn_started_at),
            )
            return True

        self._record(
            "agent_finished",
            turn_id,
            **metadata,
            transcribed_text=text,
            response=response,
            duration_ms=self._duration_ms(agent_started_at),
        )
        status = "completed"
        if response:
            tts_started_at = time.perf_counter_ns()
            self._record("tts_started", turn_id, **metadata)
            try:
                self.speak_response(response)
            except Exception as error:
                status = "completed_with_tts_error"
                self._record(
                    "tts_failed",
                    turn_id,
                    **metadata,
                    transcribed_text=text,
                    error_type=type(error).__name__,
                    error_message=str(error),
                    duration_ms=self._duration_ms(tts_started_at),
                )
            else:
                self._record(
                    "tts_finished",
                    turn_id,
                    **metadata,
                    success=True,
                    duration_ms=self._duration_ms(tts_started_at),
                )

        self._record(
            "turn_finished",
            turn_id,
            **metadata,
            transcribed_text=text,
            status=status,
            success=True,
            duration_ms=self._duration_ms(turn_started_at),
        )
        return True

    def _record(self, event_type: str, turn_id: str, **details) -> None:
        self.logger.record(
            event_type,
            turn_id,
            time_ns=time.perf_counter_ns(),
            **details,
        )

    @staticmethod
    def _duration_ms(started_at: int) -> float:
        return (time.perf_counter_ns() - started_at) / 1_000_000
