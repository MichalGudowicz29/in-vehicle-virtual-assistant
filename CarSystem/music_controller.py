from PySide6.QtCore import Q_ARG, QMetaObject, QObject, Property, QThread, Qt, Signal, Slot
import pygame

 
class MusicController(QObject):
    tracksChanged = Signal()
    contactsChanged = Signal()
    currentTrackChanged = Signal()
    isPlayingChanged = Signal()
    
    def __init__(self):
        super().__init__()
        self._tracks = [
            {
                "title": "Afryka",
                "artist": "Toto",
                "path": "music/1.mp3",
            },
            {
                "title": "Europa",
                "artist": "Fleetwood Mac",
                "path": "music/2.mp3",
            },
            {
                "title": "Ameryka",
                "artist": "a-ha",
                "path": "music/3.mp3",
            },
        ]

        self._current_track_index = 0
        self._isPlaying = False
        pygame.mixer.init()
        pygame.mixer.music.load(self._tracks[self._current_track_index]["path"])
        pygame.mixer.music.play()
        pygame.mixer.music.pause()
        
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
    @Slot()
    def next_track(self):
        if QThread.currentThread() != self.thread():
            QMetaObject.invokeMethod(
                self,
                "_next_track",
                Qt.ConnectionType.QueuedConnection,
            )
            return True

        return self._next_track()
  
    # metoda do zmiany tracka wywolywana przez next_track zeby bylo bezpiecznie watkowo
    @Slot()
    def _next_track(self):
        if not self._tracks:
            return False

        self._current_track_index = (
            self._current_track_index + 1
        ) % len(self._tracks)
        
        pygame.mixer.music.load(self._tracks[self._current_track_index]["path"])
        pygame.mixer.music.play()
        self._isPlaying = True
        self.isPlayingChanged.emit()

        self.currentTrackChanged.emit()
        print("Next track")
        return True

    # Bezpiecznie watkowa obsluga poprzedniego utworu
    @Slot()
    def previous_track(self):
        if QThread.currentThread() != self.thread():
            QMetaObject.invokeMethod(
                self,
                "_previous_track",
                Qt.ConnectionType.QueuedConnection,
            )
            return True

        return self._previous_track()
        
    # metoda do zmiany tracka wywolywana przez previous_track zeby bylo bezpiecznie watkowo
    @Slot()
    def _previous_track(self):
        if not self._tracks:
            return False

        self._current_track_index = (
            self._current_track_index - 1
        ) % len(self._tracks)
        pygame.mixer.music.load(self._tracks[self._current_track_index]["path"])
        pygame.mixer.music.play()
        self._isPlaying = True
        self.isPlayingChanged.emit()
        self.currentTrackChanged.emit()
        print("Previous track")
        return True
    
    # Bezpiecznie watkowa obsluga wyboru utworu
    @Slot(str)
    def select_track(self, title: str):
        if QThread.currentThread() != self.thread():
            QMetaObject.invokeMethod(
                self,
                "_select_track",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(str, title),
            )
            return True

        return self._select_track(title)

    # metoda do zmiany tracka wywolywana przez select_track zeby bylo bezpiecznie watkowo
    @Slot(str)
    def _select_track(self, title: str):
        index = next((i for i, t in enumerate(self._tracks) if t['title'] == title), -1)
        if index == -1:
            return False
        
        self._current_track_index = index
        pygame.mixer.music.load(self._tracks[self._current_track_index]["path"])
        pygame.mixer.music.play()
        self._isPlaying = True
        self.isPlayingChanged.emit()
        self.currentTrackChanged.emit()
        track = self._tracks[index]
        
        print(f"Selected track: {track['title']} by {track['artist']}")
        return True
        
    # Bezpiecznie watkowa obsluga pauzy/odtwarzania
    @Slot()
    def play_pause(self):
        if QThread.currentThread() != self.thread():
            QMetaObject.invokeMethod(
                self,
                "_play_pause",
                Qt.ConnectionType.QueuedConnection,
            )
            return True

        return self._play_pause()

    # metoda do zmiany stanu odtwarzania wywolywana przez play_pause zeby bylo bezpiecznie watkowo
    @Slot()
    def _play_pause(self):
        self._isPlaying = not self._isPlaying
        self.isPlayingChanged.emit()

        if self._isPlaying:
            pygame.mixer.music.unpause()
            print("Music playing")
        else:
            pygame.mixer.music.pause()
            print("Music paused")

        return True
