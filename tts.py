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
        text = speech_queue.get()
        try:
            wav, _ = tts.synthesize(text, style)
            sd.play(np.squeeze(wav))
            sd.wait()
        except Exception as error:
            speech_errors.put(error)
            print(f"TTS error: {error}")
        finally:
            speech_queue.task_done()


Thread(target=worker, daemon=True).start()


def speak(text):
    speech_queue.put(str(text))


def wait_until_speech_done():
    speech_queue.join()
    try:
        error = speech_errors.get_nowait()
    except Empty:
        return
    raise RuntimeError(f"TTS playback failed: {error}") from error
