"""whisper.cpp inference after WebRTC VAD, with the same audio timeline for files and mic."""

from collections import deque
from pathlib import Path
from queue import Empty, Queue
from time import perf_counter, sleep

import numpy as np


RATE = 16000
FRAME = 480  # WebRTC VAD requires 10, 20 or 30 ms of PCM16.
SILENCE_FRAMES = 15
MIN_SPEECH_FRAMES = 3
MODELS_DIR = Path(__file__).resolve().parent.parent / 'models/whisper'
_model = None
_model_name = None


def _get_model(size):
    global _model, _model_name
    if _model is None or _model_name != size:
        path = MODELS_DIR / f'ggml-{size}.bin'
        if not path.is_file() or path.stat().st_size == 0:
            raise FileNotFoundError(f'Brak wag Whisper: {path}. Przygotuj model przed uruchomieniem (instrukcja w README).')
        from pywhispercpp.model import Model
        # Release the previous model before allocating another on a small device.
        _model = None
        _model_name = None
        _model = Model(str(path), language='pl', no_context=True,
                       print_realtime=False, print_progress=False, print_timestamps=False,
                       greedy={'best_of': 1}, temperature=0.0)
        _model_name = size
    return _model


def _file_frames(audio, stop_event):
    started = perf_counter()
    for offset in range(0, len(audio), FRAME):
        block = audio[offset:offset + FRAME]
        stop_event.wait(max(0.0, started + (offset + len(block)) / RATE - perf_counter()))
        yield block, started + offset / RATE, None


def _microphone_frames(stop_event):
    import sounddevice as sd
    import soxr

    rate = int(sd.query_devices(kind='input')['default_samplerate'])
    resampler = soxr.ResampleStream(rate, RATE, 1, dtype='float32') if rate != RATE else None
    queue = Queue()

    def callback(indata, frames, time, status):
        captured = (perf_counter() + time.inputBufferAdcTime - time.currentTime
                    if time is not None else None)
        queue.put((indata[:, 0].copy(), captured, str(status) if status else None))

    stream = sd.InputStream(samplerate=rate, blocksize=round(rate * .03), dtype='float32',
                            channels=1, callback=callback)
    with stream:
        pending = np.empty(0, dtype=np.float32)
        started = None
        sent = 0
        last_audio_at = perf_counter()
        while True:
            try:
                audio, captured, warning = queue.get(timeout=.1)
            except Empty:
                if not stream.active or (stop_event.is_set() and
                                         perf_counter() - last_audio_at >= 1.0):
                    return
                yield None, None, None
                continue
            last_audio_at = perf_counter()
            if started is None:
                started = captured
            if warning:
                yield None, None, warning
            converted = resampler.resample_chunk(audio) if resampler is not None else audio
            pending = np.concatenate((pending, converted))
            while len(pending) >= FRAME:
                yield pending[:FRAME], started + sent / RATE if started is not None else None, None
                pending = pending[FRAME:]
                sent += FRAME


def asr_whisper(stop_event, *, model, audio_file=None, on_event=None):
    if stop_event.is_set():
        return None
    audio = None
    if audio_file is not None:
        import soundfile as sf
        import soxr
        audio, rate = sf.read(audio_file, dtype='float32', always_2d=True)
        if not len(audio):
            raise ValueError(f'Pusty plik audio: {audio_file}')
        audio = audio.mean(axis=1)
        if rate != RATE:
            audio = soxr.resample(audio, rate, RATE).astype(np.float32)
    decoder = _get_model(model)
    if stop_event.is_set():
        return None
    frames = _file_frames(audio, stop_event) if audio is not None else _microphone_frames(stop_event)
    try:
        return _recognize(frames, decoder, stop_event, on_event, audio_file is not None)
    finally:
        frames.close()


def _recognize(frames, decoder, stop_event, on_event, is_file):
    import webrtcvad

    vad = webrtcvad.Vad(2)
    history = deque(maxlen=10)
    buffer = []
    active = False
    speech_start = speech_end = None
    speech_frames = silence_frames = 0
    timing_valid = True

    def decode():
        if on_event is not None:
            on_event('decode_start')   # splits "end of speech -> text" into endpointing and decoding
        segments = decoder.transcribe(np.concatenate(buffer).astype(np.float32))
        text = ''.join(segment.text for segment in segments).strip()
        ready = perf_counter()
        if text and on_event is not None:
            if timing_valid and speech_start is not None and speech_end is not None:
                on_event('speech_start', at=speech_start)
                on_event('speech_end', at=speech_end)
            else:
                on_event('asr_warning', warning='Brak wiarygodnych granic mowy WebRTC VAD.')
            on_event('transcription_ready', at=ready, text=text)
        return text or None

    for samples, at, warning in frames:
        if stop_event.is_set() and not active:
            return None
        if warning:
            timing_valid = False
            if on_event is not None:
                on_event('asr_warning', warning=warning)
        if samples is None:
            continue
        if at is None:
            timing_valid = False
        if is_file and at is not None:
            # A stop request still lets an already detected utterance finish at 1x.
            sleep(max(0.0, at + len(samples) / RATE - perf_counter()))
        pcm = (np.clip(samples, -1, 1) * 32767).astype('<i2').tobytes()
        pcm += bytes(max(0, FRAME * 2 - len(pcm)))
        speech = vad.is_speech(pcm, RATE)
        if not active:
            history.append(samples)
            if not speech:
                continue
            active = True
            speech_start = at
            buffer = list(history)
            history.clear()
            if on_event is not None:
                on_event('speech_detected')
        else:
            buffer.append(samples)
        if speech:
            speech_frames += 1
            speech_end = at + len(samples) / RATE if at is not None else None
            silence_frames = 0
        else:
            silence_frames += 1
        if silence_frames >= SILENCE_FRAMES:
            if speech_frames >= MIN_SPEECH_FRAMES:
                text = decode()
                if text:
                    return text
                if is_file:
                    raise ValueError('Whisper nie rozpoznał mowy w pliku.')
            active = False
            buffer = []
            speech_frames = silence_frames = 0
            speech_start = speech_end = None
    # Only a file EOF is a valid endpoint; a lost microphone leaves a truncated turn.
    if is_file and active and speech_frames >= MIN_SPEECH_FRAMES:
        text = decode()
        if text:
            return text
    if is_file:
        raise ValueError('Nie rozpoznano mowy w pliku (Whisper / WebRTC VAD).')
    return None
