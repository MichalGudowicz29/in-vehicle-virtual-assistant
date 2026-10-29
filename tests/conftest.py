"""Exercise application logic without a sound card or private music files."""

import os
import wave

import pytest

os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")


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
