import pygame
from PySide6.QtCore import QObject, Property, Signal, Slot

from .gui_thread import init_gui_thread, on_gui_thread


class MusicController(QObject):
    """Local music library played with pygame; state is exposed to QML."""
    tracksChanged = Signal()
    currentTrackChanged = Signal()
    isPlayingChanged = Signal()

    def __init__(self, initial_track_index=0):
        super().__init__()
        init_gui_thread(self)
        self._tracks = [
            {"title": "Christmas Eve", "artist": "Toto", "path": "music/1.mp3"},
            {"title": "Chill song", "artist": "Fleetwood Mac", "path": "music/2.mp3"},
            {"title": "Dynamic music", "artist": "a-ha", "path": "music/3.mp3"},
        ]
        self._current_track_index = initial_track_index
        self._isPlaying = False
        pygame.mixer.init()
        pygame.mixer.music.load(self._tracks[self._current_track_index]["path"])
        pygame.mixer.music.play()
        pygame.mixer.music.pause()
        self._track_loaded = True

    @Property(list, notify=tracksChanged)
    def tracks(self):
        return self._tracks

    @Property(int, notify=currentTrackChanged)
    def currentTrackIndex(self):
        return self._current_track_index

    @Property(bool, notify=isPlayingChanged)
    def isPlaying(self):
        return self._isPlaying

    @Slot(result=bool)
    @on_gui_thread
    def next_track(self):
        if not self._tracks:
            return False
        return self._load_track((self._current_track_index + 1) % len(self._tracks))

    @Slot(result=bool)
    @on_gui_thread
    def previous_track(self):
        if not self._tracks:
            return False
        return self._load_track((self._current_track_index - 1) % len(self._tracks))

    @Slot(str, result=bool)
    @on_gui_thread
    def select_track(self, title: str):
        index = next((i for i, t in enumerate(self._tracks) if t['title'] == title), -1)
        if index == -1:
            return False
        return self._load_track(index)

    def _load_track(self, index):
        # A failed load can discard the previous audio; never resume an uncommitted track.
        self._track_loaded = False
        try:
            pygame.mixer.music.load(self._tracks[index]["path"])
            pygame.mixer.music.play()
        except (pygame.error, OSError):
            try:
                pygame.mixer.music.stop()
            except pygame.error:
                pass
            if self._isPlaying:
                self._isPlaying = False
                self.isPlayingChanged.emit()
            return False

        self._track_loaded = True
        self._current_track_index = index
        self._isPlaying = True
        self.isPlayingChanged.emit()
        self.currentTrackChanged.emit()
        return True

    @Slot(bool, result=bool)
    @on_gui_thread
    def set_playback(self, playing: bool):
        """Absolute state: repeating "pause" keeps music paused (voice commands)."""
        if self._isPlaying == playing:
            return True
        if playing and not self._track_loaded:
            return self._load_track(self._current_track_index)
        try:
            if playing:
                pygame.mixer.music.unpause()
            else:
                pygame.mixer.music.pause()
        except pygame.error:
            return False
        self._isPlaying = playing
        self.isPlayingChanged.emit()
        return True

    @Slot(result=bool)
    @on_gui_thread
    def play_pause(self):
        """Toggle (touch button)."""
        return self.set_playback(not self._isPlaying)
