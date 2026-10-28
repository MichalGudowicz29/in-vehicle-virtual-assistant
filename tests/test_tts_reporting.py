import importlib.util
import sys
from types import SimpleNamespace

import numpy as np
import pytest


def load_tts(monkeypatch):
    class FakeTTS:
        sample_rate = 24000
        def get_voice_style(self, name):
            return name
        def synthesize(self, text, style):
            return np.zeros((1, 100)), 0
    monkeypatch.setitem(sys.modules, 'supertonic', SimpleNamespace(TTS=lambda **kwargs: FakeTTS()))
    # Load an isolated module so a test never downloads a real model.
    spec = importlib.util.spec_from_file_location('test_tts_module', 'tts.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_tts_reports_synthesis_and_playback_separately(monkeypatch):
    module = load_tts(monkeypatch)
    events = []
    samples = []
    monkeypatch.setattr(module.sd, 'play', lambda wav, samplerate: samples.append(samplerate))
    monkeypatch.setattr(module.sd, 'wait', lambda: None)
    module.speak('Gotowe', on_event=lambda kind, **data: events.append(kind))
    module.wait_until_speech_done()
    assert events == ['tts_start', 'tts_end', 'audio_start', 'audio_end']
    assert samples == [24000]


def test_tts_failure_is_logged_and_propagated(monkeypatch):
    module = load_tts(monkeypatch)
    def fail(*args):
        raise ValueError('synthesis failed')
    monkeypatch.setattr(module.tts, 'synthesize', fail)
    events = []
    module.speak('Gotowe', on_event=lambda kind, **data: events.append(kind))
    with pytest.raises(RuntimeError, match='synthesis failed'):
        module.wait_until_speech_done()
    assert events == ['tts_start', 'tts_error']
