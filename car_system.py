from PySide6.QtCore import Q_ARG, QMetaObject, QObject, Property, QThread, Qt, Signal, Slot

class CarSystem(QObject):
    currentScreenChanged = Signal()
    destinationChanged = Signal()
    
    navigationScreenRequested = Signal()
    
    def __init__(self):
        super().__init__()
        self._screen = "home"
        self._destination = ""
        
    #wlasciwosci dla QML
    @Property(str, notify=currentScreenChanged)
    def currentScreen(self):
        return self._screen
    
    @Property(str, notify=destinationChanged)
    def destination(self):
        return self._destination
    
    def _set_screen(self, name: str):
        if self._screen != name:
            self._screen = name
            self.currentScreenChanged.emit()
            
    # logika wspolna dla QML i asystenta
    @Slot(str)
    def set_destination(self, address: str):
        if QThread.currentThread() != self.thread():
            QMetaObject.invokeMethod(
                self,
                "_set_destination",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(str, address),
            )
            return

        self._set_destination(address)

    @Slot(str)
    def _set_destination(self, address: str):
        self._destination = address
        self.destinationChanged.emit()
        self.navigationScreenRequested.emit()
        print(f"Set destination to {address}")


    # Music
    @Slot()
    def play_pause(self): 
        print("Play/Pause")

    @Slot()
    def next_track(self): 
        print("Next track")

    @Slot()
    def previous_track(self): 
        print("Previous track")

    @Slot(int)
    def seek(self, seconds: int): 
        print(f"Seek {seconds} seconds")

    # Calls
    @Slot(str)
    def find_contact(self, name: str): 
        print(f"Find contact {name}")

    @Slot(str, str)
    def call_contact(self, name: str, number_type: str | None = None): 
        print(f"Call contact {name} with number type {number_type}")

    # Navigation
    @Slot(str, str)
    def save_address(self, label: str, address: str): print(f"Save address {label}: {address}")
