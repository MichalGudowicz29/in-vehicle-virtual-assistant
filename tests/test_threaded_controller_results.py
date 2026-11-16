from typing import cast
import pytest

from CarSystem.car_system import CarSystem
from CarSystem.navigation_controller import NavigationController


@pytest.mark.parametrize('playing', [False, True])
def test_background_absolute_playback_returns_success_and_preserves_requested_state(qt_call, playing):
    car = CarSystem()
    assert qt_call(lambda: car.music.set_playback(playing)) is True
    assert qt_call(lambda: car.music.set_playback(playing)) is True
    assert car.music.isPlaying is playing


def test_background_track_load_failure_returns_false_without_changing_track(qt_call, monkeypatch):
    import pygame
    car = CarSystem()
    car.music.set_playback(True)

    def fail_load(path):
        raise pygame.error('broken track')

    monkeypatch.setattr(pygame.mixer.music, 'load', fail_load)
    assert qt_call(lambda: car.music.next_track()) is False
    assert car.music.currentTrackIndex == 0
    assert car.music.isPlaying is False


def test_background_music_action_returns_its_real_failure(qt_call):
    car = CarSystem()

    success = qt_call(
        lambda: car.music.select_track("Unknown track")
    )

    assert success is False


def test_background_contact_action_returns_its_real_failure(qt_call):
    car = CarSystem()

    success = qt_call(
        lambda: car.contacts.call_contact("Robert Lewandowski", "work")
    )

    assert success is False


def test_background_navigation_action_returns_its_real_failure(qt_call):
    car = CarSystem()
    navigation = cast(NavigationController, car.navigation)

    success = qt_call(
        lambda: navigation.set_destination("Unknown place")
    )

    assert success is False
