from PySide6.QtCore import QObject, Slot


class QmlBackend(QObject):
    def __init__(self, car):
        super().__init__()
        self.car = car

    @Slot()
    def playPause(self):
        self.car.play_pause()

    @Slot()
    def nextTrack(self):
        self.car.next_track()

    @Slot()
    def previousTrack(self):
        self.car.previous_track()

    @Slot(str, str)
    def callContact(self, name, number_type):
        self.car.call_contact(name, number_type)

    @Slot(str)
    def setDestination(self, address):
        self.car.set_destination(address)
