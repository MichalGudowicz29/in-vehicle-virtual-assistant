
import threading
from unittest.mock import Mock

import asr


class FakeRawInputStream:
    """Symulowany strumień audio."""

    def __init__(self, *, callback, **kwargs):
        self.callback = callback

    def __enter__(self):
        # Symulujemy odebranie próbki audio.
        self.callback(b"\x00\x00", 1, None, None)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


def test_listen_returns_recognized_text(monkeypatch):
    # Symulujemy ustawienia urządzenia audio.
    monkeypatch.setattr(
        asr.sd,
        "query_devices",
        lambda **kwargs: {"default_samplerate": 16000},
    )

    # Nie otwieramy prawdziwego mikrofonu.
    monkeypatch.setattr(
        asr.sd, "RawInputStream", FakeRawInputStream
    )

    # Nie ładujemy prawdziwego modelu Vosk.
    monkeypatch.setattr(asr, "_get_model", lambda: object())

    # Symulujemy wynik rozpoznawania mowy.
    recognizer = Mock()
    recognizer.AcceptWaveform.return_value = True
    recognizer.Result.return_value = '{"text": "włącz nawigację"}'

    monkeypatch.setattr(
        asr,
        "KaldiRecognizer",
        lambda model, samplerate: recognizer,
    )

    result = asr.listen(threading.Event())

    assert result == "włącz nawigację"
    recognizer.AcceptWaveform.assert_called_once()
