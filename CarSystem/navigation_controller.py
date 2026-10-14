from PySide6.QtCore import Q_ARG, QMetaObject, QMetaType, QObject, Property, QThread, Qt, Signal, Slot

class NavigationController(QObject):
    destinationChanged = Signal()
    mapScreenRequested = Signal()

    def __init__(self):
        super().__init__()
        self._destination = ""

    @Property(str, notify=destinationChanged)
    def destination(self):
        return self._destination

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
        self.mapScreenRequested.emit()
        print(f"Set destination to {address}")