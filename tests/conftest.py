"""Exercise application logic without a sound card or private music files."""

import os
import wave
import threading
import time

import pytest

os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

# Test fixtures stay independent of the user's .env and work in CI without it.
os.environ["OLLAMA_MODEL"] = "test-local-default:2b"
os.environ["ASR_MODEL"] = "vosk"


@pytest.fixture(scope="session")
def music_file(tmp_path_factory):
    path = tmp_path_factory.mktemp("music") / "silence.wav"
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(bytes(3200))
    return path


@pytest.fixture(autouse=True)
def test_music(monkeypatch, music_file):
    import pygame

    # Keep the real mixer/decoder, replacing only the external test asset.
    load = pygame.mixer.music.load
    monkeypatch.setattr(pygame.mixer.music, "load", lambda _path: load(str(music_file)))


@pytest.fixture
def qt_call():
    """Run a worker action while Qt handles controller calls on the main thread."""
    from PySide6.QtCore import QCoreApplication

    app = QCoreApplication.instance() or QCoreApplication([])

    def call(action):
        result = {}

        def run_action():
            try:
                result['value'] = action()
            except BaseException as error:
                result['error'] = error

        worker = threading.Thread(target=run_action, daemon=True)
        worker.start()
        deadline = time.monotonic() + 5
        while worker.is_alive() and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.001)
        worker.join(timeout=0.1)
        assert not worker.is_alive(), 'Controller call did not finish.'
        if 'error' in result:
            raise result['error']
        return result['value']

    return call
