from queue import Empty, Queue
from threading import Thread

import numpy as np
import sounddevice as sd
from supertonic import TTS


tts = TTS(auto_download=True)
style = tts.get_voice_style("M2")
speech_queue = Queue()
speech_errors = Queue()


def worker():
    while True:
        text, on_event = speech_queue.get()
        try:
            if on_event is not None:
                on_event("tts_start")
            wav, _ = tts.synthesize(text, style)
            if on_event is not None:
                on_event("tts_end")
                on_event("audio_start")
            sd.play(np.squeeze(wav), samplerate=tts.sample_rate)
            sd.wait()
            if on_event is not None:
                on_event("audio_end")
        except Exception as error:
            if on_event is not None:
                on_event("tts_error", error=str(error))
            speech_errors.put(error)
            print(f"TTS error: {error}")
        finally:
            speech_queue.task_done()


Thread(target=worker, daemon=True).start()


def speak(text, on_event=None):
    speech_queue.put((str(text), on_event))


def wait_until_speech_done():
    speech_queue.join()
    try:
        error = speech_errors.get_nowait()
    except Empty:
        return
    raise RuntimeError(f"TTS playback failed: {error}") from error
