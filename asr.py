import json
import queue
import threading
from pathlib import Path
from time import perf_counter, sleep

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
                    _report_transcription(text, result.get("result", []),
                                          first_audio_at if timing_valid else None,
                                          ready_at, on_event)
                    return text
                speech_started = False
            elif json.loads(recognizer.PartialResult()).get("partial", "").strip():
                if not speech_started and on_event is not None:
                    on_event("speech_detected")
                # Dokończ rozpoznaną wypowiedź, nawet jeśli użytkownik kliknął Zakończ.
                speech_started = True

    return None


def listen_file(path: Path, stop_event: threading.Event, on_event=None) -> str | None:
    if stop_event.is_set():
        return None

    import soundfile as sf

    with sf.SoundFile(path) as source:
        if source.frames == 0:
            raise ValueError(f"Pusty plik audio: {path}")
        recognizer = KaldiRecognizer(_get_model(), source.samplerate)
        if on_event is not None:
            recognizer.SetWords(True)
        started_at = perf_counter()
        frames_sent = 0
        speech_started = False
        result = {}
        for block in source.blocks(blocksize=8000, dtype="int16", always_2d=True):
            # Mean uses floating point, so stereo addition cannot overflow int16.
            pcm = block.mean(axis=1).astype("<i2").tobytes()
            frames_sent += len(block)
            deadline = started_at + frames_sent / source.samplerate
            if stop_event.wait(max(0.0, deadline - perf_counter())):
                if not speech_started:
                    return None
                # Finish the started turn at 1x even after a shutdown request.
                sleep(max(0.0, deadline - perf_counter()))
            if recognizer.AcceptWaveform(pcm):
                result = json.loads(recognizer.Result())
                if result.get("text", "").strip():
                    break
                speech_started = False
            elif json.loads(recognizer.PartialResult()).get("partial", "").strip():
                if not speech_started and on_event is not None:
                    on_event("speech_detected")
                speech_started = True

        # EOF, unlike the microphone, may arrive without an endpoint's trailing silence.
        if not result.get("text", "").strip():
            result = json.loads(recognizer.FinalResult())
        ready_at = perf_counter()
        text = result.get("text", "").strip()
        if not text:
            raise ValueError(f"Nie rozpoznano mowy w pliku: {path}")
        _report_transcription(text, result.get("result", []), started_at, ready_at, on_event)
        return text


def _report_transcription(text, words, audio_started_at, ready_at, on_event):
    if on_event is None:
        return
    if words and audio_started_at is not None:
        on_event("speech_start", at=audio_started_at + words[0]["start"])
        on_event("speech_end", at=audio_started_at + words[-1]["end"])
    else:
        on_event("asr_warning", warning="Brak wiarygodnych granic mowy Vosk.")
    on_event("transcription_ready", at=ready_at, text=text)
