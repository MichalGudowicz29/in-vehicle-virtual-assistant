from PySide6.QtCore import Q_ARG, QMetaObject, QObject, Property, QThread, Qt, Signal, Slot
from .music_controller import MusicController
from .navigation_controller import NavigationController

class CarSystem(QObject):
    currentScreenChanged = Signal()
    destinationChanged = Signal()
    mapScreenRequested = Signal()
    
    contactsChanged = Signal()
    
    
    def __init__(self):
        super().__init__()
        self._music = MusicController()
        self._contacts = ...
        self._navigation = NavigationController()
        self._screen = "home"
        self._destination = ""

    @Property(MusicController, constant=True)
    def music(self):
        return self._music
    
    @Property(NavigationController, constant=True)
    def navigation(self):
        return self._navigation
    


