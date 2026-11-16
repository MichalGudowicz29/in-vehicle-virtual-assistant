from PySide6.QtCore import Q_ARG, Q_RETURN_ARG, QMetaObject, QObject, Property, QThread, Qt, Signal, Slot
import pygame

 
class MusicController(QObject):
    tracksChanged = Signal()
    contactsChanged = Signal()
    currentTrackChanged = Signal()
    isPlayingChanged = Signal()
    
    def __init__(self, initial_track_index=0):
        super().__init__()
        self._tracks = [
            {
                "title": "Christmas Eve",
                "artist": "Toto",
                "path": "music/1.mp3",
            },
            {
                "title": "Chill song",
                "artist": "Fleetwood Mac",
                "path": "music/2.mp3",
            },
            {
                "title": "Dynamic music",
                "artist": "a-ha",
                "path": "music/3.mp3",
            },
        ]

        self._current_track_index = initial_track_index
        self._isPlaying = False
        pygame.mixer.init()
        pygame.mixer.music.load(self._tracks[self._current_track_index]["path"])
        pygame.mixer.music.play()
        pygame.mixer.music.pause()
        self._track_loaded = True
        
    # Muzyka
    
    # Wystawienie listy utworów
    @Property(list, notify=tracksChanged)
    def tracks(self):
        return self._tracks
    
    # Wystawienie indeksu obecnego utworu
    @Property(int, notify=currentTrackChanged)
    def currentTrackIndex(self):
        return self._current_track_index

    # Wystawienie informacji o stanie odtwarzania
    @Property(bool, notify=isPlayingChanged)
    def isPlaying(self):
        return self._isPlaying

    # Bezpiecznie watkowa obsluga nastepnego utworu
    @Slot(result=bool)
    def next_track(self):
        if QThread.currentThread() != self.thread():
            return QMetaObject.invokeMethod(
                self,
                "_next_track",
                Qt.ConnectionType.BlockingQueuedConnection,
                Q_RETURN_ARG(bool),
            )

        return self._next_track()
  
    # metoda do zmiany tracka wywolywana przez next_track zeby bylo bezpiecznie watkowo
    @Slot(result=bool)
    def _next_track(self):
        if not self._tracks:
            return False

        index = (
            self._current_track_index + 1
        ) % len(self._tracks)
        return self._load_track(index)

    # Bezpiecznie watkowa obsluga poprzedniego utworu
    @Slot(result=bool)
    def previous_track(self):
        if QThread.currentThread() != self.thread():
            return QMetaObject.invokeMethod(
                self,
                "_previous_track",
                Qt.ConnectionType.BlockingQueuedConnection,
                Q_RETURN_ARG(bool),
            )

        return self._previous_track()
        
    # metoda do zmiany tracka wywolywana przez previous_track zeby bylo bezpiecznie watkowo
    @Slot(result=bool)
    def _previous_track(self):
        if not self._tracks:
            return False

        index = (
            self._current_track_index - 1
        ) % len(self._tracks)
        return self._load_track(index)
    
    # Bezpiecznie watkowa obsluga wyboru utworu
    @Slot(str, result=bool)
    def select_track(self, title: str):
        if QThread.currentThread() != self.thread():
            return QMetaObject.invokeMethod(
                self,
                "_select_track",
                Qt.ConnectionType.BlockingQueuedConnection,
                Q_RETURN_ARG(bool),
                Q_ARG(str, title),
            )

        return self._select_track(title)

    # metoda do zmiany tracka wywolywana przez select_track zeby bylo bezpiecznie watkowo
    @Slot(str, result=bool)
    def _select_track(self, title: str):
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
    def set_playback(self, playing: bool):
        if QThread.currentThread() != self.thread():
            return QMetaObject.invokeMethod(
                self,
                "_set_playback",
                Qt.ConnectionType.BlockingQueuedConnection,
                Q_RETURN_ARG(bool),
                Q_ARG(bool, playing),
            )

        return self._set_playback(playing)

    @Slot(bool, result=bool)
    def _set_playback(self, playing: bool):
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
        
    # Bezpiecznie watkowa obsluga pauzy/odtwarzania
    @Slot(result=bool)
    def play_pause(self):
        if QThread.currentThread() != self.thread():
            return QMetaObject.invokeMethod(
                self,
                "_play_pause",
                Qt.ConnectionType.BlockingQueuedConnection,
                Q_RETURN_ARG(bool),
            )

        return self._play_pause()

    # metoda do zmiany stanu odtwarzania wywolywana przez play_pause zeby bylo bezpiecznie watkowo
    @Slot(result=bool)
    def _play_pause(self):
        return self._set_playback(not self._isPlaying)
