from PySide6.QtCore import QObject, Property

from .contact_controller import ContactController
from .music_controller import MusicController
from .navigation_controller import NavigationController


class CarSystem(QObject):
    """Simulated head unit: the single object shared by QML (touch) and the assistant (voice)."""

    def __init__(self, *, initial_music_track_index=0):
        super().__init__()
        self._music = MusicController(initial_track_index=initial_music_track_index)
        self._contacts = ContactController()
        self._navigation = NavigationController()

    @Property(MusicController, constant=True)
    def music(self):
        return self._music

    @Property(NavigationController, constant=True)
    def navigation(self):
        return self._navigation

    @Property(ContactController, constant=True)
    def contacts(self):
        return self._contacts
