"""One ASR interface for microphone and paced audio files; backends load lazily."""

from pathlib import Path
from threading import Event

WHISPER_MODELS = {
    'whisper-small': 'small',
    'whisper-medium': 'medium',
    'whisper-large': 'large-v3',
    'whisper-large-v3-turbo-q5_0': 'large-v3-turbo-q5_0',
}
ASR_MODELS = ('vosk', *WHISPER_MODELS)
# Manual use (microphone). The measurement series keeps its own matrix in experiments/runner.py.
MANUAL_ASR = 'whisper-large-v3-turbo-q5_0'


def resolve_model(asr: str | None = None) -> str:
    import config

    name = config.ASR_MODEL if asr is None else asr
    if name not in ASR_MODELS:
        raise ValueError(f"Nieznany ASR: {name!r}. Dostępne: {', '.join(ASR_MODELS)}")
    return name


def model_label(asr: str) -> str:
    return 'Vosk small-pl-0.22' if asr == 'vosk' else f'Whisper {WHISPER_MODELS[asr]} (whisper.cpp)'


def listen(stop_event: Event, on_event=None, *, asr: str | None = None) -> str | None:
    return _listen(stop_event, on_event, resolve_model(asr), None)


def listen_file(path: Path, stop_event: Event, on_event=None, *, asr: str | None = None) -> str | None:
    return _listen(stop_event, on_event, resolve_model(asr), path)


def _listen(stop_event, on_event, asr, path):
    if asr == 'vosk':
        from .vosk import asr_vosk, asr_vosk_file
        if path is None:
            return asr_vosk(stop_event, on_event=on_event)
        return asr_vosk_file(path, stop_event, on_event=on_event)
    from .whisper import asr_whisper
    return asr_whisper(stop_event, model=WHISPER_MODELS[asr], audio_file=path, on_event=on_event)
