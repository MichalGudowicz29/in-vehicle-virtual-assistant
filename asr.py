import json
import queue
import threading
from pathlib import Path
from time import perf_counter

from vosk import KaldiRecognizer, Model


MODEL_PATH = Path(__file__).resolve().parent / "models/vosk-model-small-pl-0.22"
_model = None


def _get_model():
    global _model
    if _model is None:
        _model = Model(str(MODEL_PATH))
    return _model



#TODO Przejsc na whisper large
def listen(stop_event: threading.Event, on_event=None) -> str | None:
    if stop_event.is_set():
        return None

    import sounddevice as sd

    samplerate = int(sd.query_devices(kind="input")["default_samplerate"])
    recognizer = KaldiRecognizer(_get_model(), samplerate)
    if on_event is not None:
        recognizer.SetWords(True)
    audio_queue = queue.Queue()
    speech_started = False
    first_audio_at = None
    timing_valid = True

    def audio_callback(indata, frames, time, status):
        # PortAudio timestamps share a clock; map the first captured sample to ours.
        captured_at = (perf_counter() + time.inputBufferAdcTime - time.currentTime
                       if time is not None else None)
        audio_queue.put((bytes(indata), captured_at, str(status) if status else None))

    with sd.RawInputStream(
        samplerate=samplerate,
        blocksize=8000,
        dtype="int16",
        channels=1,
        callback=audio_callback,
    ):
        while not stop_event.is_set() or speech_started:
            try:
                data, captured_at, warning = audio_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            if first_audio_at is None:
                first_audio_at = captured_at
            if warning:
                timing_valid = False
                if on_event is not None:
                    on_event("asr_warning", warning=warning)

            if recognizer.AcceptWaveform(data):
                result = json.loads(recognizer.Result())
                text = result.get("text", "").strip()
                if text:
                    ready_at = perf_counter()
                    if on_event is not None:
                        words = result.get("result", [])
                        if words and first_audio_at is not None and timing_valid:
                            on_event("speech_start", at=first_audio_at + words[0]["start"])
                            on_event("speech_end", at=first_audio_at + words[-1]["end"])
                        else:
                            on_event("asr_warning", warning="Brak wiarygodnych granic mowy Vosk.")
                        on_event("transcription_ready", at=ready_at, text=text)
                    return text
                speech_started = False
            elif json.loads(recognizer.PartialResult()).get("partial", "").strip():
                if not speech_started and on_event is not None:
                    on_event("speech_detected")
                # Dokończ rozpoznaną wypowiedź, nawet jeśli użytkownik kliknął Zakończ.
                speech_started = True

    return None
