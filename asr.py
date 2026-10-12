import json
import queue
import threading
from pathlib import Path

import sounddevice as sd
from vosk import KaldiRecognizer, Model


MODEL_PATH = Path(__file__).resolve().parent / "models/vosk-model-small-pl-0.22"
_model = None


def _get_model():
    global _model
    if _model is None:
        _model = Model(str(MODEL_PATH))
    return _model


def listen(stop_event: threading.Event) -> str | None:
    samplerate = int(sd.query_devices(kind="input")["default_samplerate"])
    recognizer = KaldiRecognizer(_get_model(), samplerate)
    audio_queue = queue.Queue()

    def audio_callback(indata, frames, time, status):
        audio_queue.put(bytes(indata))

    with sd.RawInputStream(
        samplerate=samplerate,
        blocksize=8000,
        dtype="int16",
        channels=1,
        callback=audio_callback,
    ):
        while not stop_event.is_set():
            try:
                data = audio_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            if recognizer.AcceptWaveform(data):
                text = json.loads(recognizer.Result()).get("text", "").strip()
                if text:
                    return text

    return None
