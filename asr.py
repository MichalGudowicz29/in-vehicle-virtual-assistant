import json
import queue
import threading

import sounddevice as sd
from pynput import keyboard
from vosk import KaldiRecognizer, Model


model = Model("models/vosk-model-small-pl-0.22")
samplerate = int(sd.query_devices(kind="input")["default_samplerate"])


def listen() -> str | None:
    """Record while V is held and return one transcript after it is released."""
    recognizer = KaldiRecognizer(model, samplerate)
    audio_queue = queue.Queue()
    recording = threading.Event()
    cancelled = threading.Event()

    def audio_callback(indata, frames, time, status):
        if recording.is_set():
            audio_queue.put(bytes(indata))

    def on_press(key):
        if key == keyboard.Key.esc:
            cancelled.set()
            recording.clear()
            return False

        if getattr(key, "char", None) and key.char.lower() == "v":
            recording.set()

    def on_release(key):
        if getattr(key, "char", None) and key.char.lower() == "v":
            recording.clear()

    print("V push to talk, ESC exit")
    with sd.RawInputStream(
        samplerate=samplerate,
        blocksize=8000,
        dtype="int16",
        channels=1,
        callback=audio_callback,
    ):
        with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
            while listener.is_alive() and not cancelled.is_set():
                if recording.wait(timeout=0.1):
                    break

            if cancelled.is_set():
                return None

            while recording.is_set():
                try:
                    recognizer.AcceptWaveform(audio_queue.get(timeout=0.1))
                except queue.Empty:
                    continue

            while True:
                try:
                    recognizer.AcceptWaveform(audio_queue.get_nowait())
                except queue.Empty:
                    break

            if cancelled.is_set():
                return None

            return json.loads(recognizer.FinalResult()).get("text", "")
