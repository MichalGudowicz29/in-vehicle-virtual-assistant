from unittest.mock import Mock

import pygame
import pytest

from CarSystem.music_controller import MusicController


@pytest.mark.parametrize('playing', [False, True])
def test_set_playback_is_idempotent(monkeypatch, playing):
    music = MusicController()
    changed = Mock()
    music.isPlayingChanged.connect(changed)
    pause = Mock()
    unpause = Mock()
    monkeypatch.setattr(pygame.mixer.music, 'pause', pause)
    monkeypatch.setattr(pygame.mixer.music, 'unpause', unpause)

    assert music.set_playback(playing) is True
    assert music.set_playback(playing) is True
    assert music.isPlaying is playing
    assert changed.call_count == int(playing)
    assert pause.call_count == 0
    assert unpause.call_count == int(playing)


def test_repeated_pause_after_resume_does_not_restart_music(monkeypatch):
    music = MusicController()
    assert music.set_playback(True)
    pause = Mock()
    unpause = Mock()
    monkeypatch.setattr(pygame.mixer.music, 'pause', pause)
    monkeypatch.setattr(pygame.mixer.music, 'unpause', unpause)

    assert music.set_playback(False) is True
    assert music.set_playback(False) is True
    assert music.isPlaying is False
    pause.assert_called_once_with()
    unpause.assert_not_called()


@pytest.mark.parametrize('method,args', [
    ('next_track', ()), ('previous_track', ()), ('select_track', ('Chill song',)),
])
@pytest.mark.parametrize('operation', ['load', 'play'])
@pytest.mark.parametrize('error_type', [pygame.error, FileNotFoundError])
def test_track_failure_preserves_index_and_stops_playback(monkeypatch, method, args, operation, error_type):
    music = MusicController()
    assert music.play_pause()
    changed = Mock()
    track_changed = Mock()
    music.isPlayingChanged.connect(changed)
    music.currentTrackChanged.connect(track_changed)
    stop = Mock()
    monkeypatch.setattr(pygame.mixer.music, 'stop', stop)
    monkeypatch.setattr(pygame.mixer.music, operation, Mock(side_effect=error_type('unavailable')))

    assert getattr(music, method)(*args) is False
    assert music.currentTrackIndex == 0
    assert music.isPlaying is False
    changed.assert_called_once_with()
    track_changed.assert_not_called()
    stop.assert_called_once_with()


@pytest.mark.parametrize('operation', ['load', 'play'])
def test_resume_after_failed_change_reloads_last_committed_track(monkeypatch, operation):
    music = MusicController()
    with monkeypatch.context() as failure:
        failure.setattr(pygame.mixer.music, operation, Mock(side_effect=pygame.error('broken')))
        assert music.next_track() is False
    load = Mock()
    play = Mock()
    unpause = Mock()
    monkeypatch.setattr(pygame.mixer.music, 'load', load)
    monkeypatch.setattr(pygame.mixer.music, 'play', play)
    monkeypatch.setattr(pygame.mixer.music, 'unpause', unpause)

    assert music.set_playback(True) is True
    assert music.isPlaying is True
    load.assert_called_once_with('music/1.mp3')
    play.assert_called_once_with()
    unpause.assert_not_called()


@pytest.mark.parametrize('playing', [False, True])
def test_playback_failure_preserves_state(monkeypatch, playing):
    music = MusicController()
    assert music.set_playback(not playing)
    changed = Mock()
    music.isPlayingChanged.connect(changed)
    operation = 'unpause' if playing else 'pause'
    monkeypatch.setattr(pygame.mixer.music, operation, Mock(side_effect=pygame.error('broken')))

    assert music.set_playback(playing) is False
    assert music.isPlaying is not playing
    changed.assert_not_called()


@pytest.mark.parametrize('method,args,index', [
    ('next_track', (), 1), ('previous_track', (), 2), ('select_track', ('Chill song',), 1),
])
def test_successful_track_change_commits_state(method, args, index):
    music = MusicController()
    changed = Mock()
    music.currentTrackChanged.connect(changed)

    assert getattr(music, method)(*args) is True
    assert music.currentTrackIndex == index
    assert music.isPlaying is True
    changed.assert_called_once_with()
