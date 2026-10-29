from PySide6.QtCore import Q_ARG, Q_RETURN_ARG, QMetaObject, QObject, Property, QThread, Qt, Signal, Slot


class NavigationController(QObject):
    destinationChanged = Signal()
    routePointsChanged = Signal()
    stopsChanged = Signal()
    mapScreenRequested = Signal()

    def __init__(self):
        super().__init__()
        self._destination = ""
        self._start = {
            "label": "start",
            "address": "ul. Startowa 1, Szczecin",
            "lat": 53.44701694345204,
            "lon": 14.492347537788525,
        }
        self._places = {
            "ul. stacyjna 10, szczecin": {
                "address": "ul. Stacyjna 10, Szczecin",
                "lat": 53.4485,
                "lon": 14.5100,
            },
            "ul. przystankowa 20, szczecin": {
                "address": "ul. Przystankowa 20, Szczecin",
                "lat": 53.4380,
                "lon": 14.5300,
            },
            "ul. żołnierska 47, szczecin": {
                "address": "ul. Żołnierska 47, Szczecin",
                "lat": 53.4285,
                "lon": 14.5528,
            },
        }
        self._stops = []
        self._destination_coordinates = None
        
    @Property(dict, notify=destinationChanged)
    def places_list(self):
        return self._places

    @Property(str, notify=destinationChanged)
    def destination(self):
        return self._destination
    

    @Property(list, notify=routePointsChanged)
    def routePoints(self):
        points = [self._start, *self._stops]
        if self._destination_coordinates is not None:
            points.append(self._destination_coordinates)
        return [point.copy() for point in points]

    @Property(list, notify=stopsChanged)
    def stops(self):
        return [stop.copy() for stop in self._stops]

    @Slot(str, result=bool)
    def set_destination(self, address: str):
        if QThread.currentThread() != self.thread():
            return QMetaObject.invokeMethod(
                self,
                "_set_destination",
                Qt.ConnectionType.BlockingQueuedConnection,
                Q_RETURN_ARG(bool),
                Q_ARG(str, address),
            )

        return self._set_destination(address)

    @Slot(str, result=bool)
    def _set_destination(self, address: str):
        place = self.get_coordinates(address)
        if place is None:
            return False

        self._destination = address
        self._destination_coordinates = {
            "label": place["address"],
            "address": place["address"],
            "lat": place["latitude"],
            "lon": place["longitude"],
        }
        self._destination = place["address"]
        self.destinationChanged.emit()
        self.routePointsChanged.emit()
        self.mapScreenRequested.emit()
        print(f"Set destination to {address}")
        return True

    @Slot(str, result="QVariant")
    def get_coordinates(self, address: str):
        place = self._places.get(address.strip().lower())
        if place is None:
            return None
        return {
            "latitude": place["lat"],
            "longitude": place["lon"],
            "address": place["address"],
        }

    @Slot(str, result=bool)
    def add_stop(self, address: str):
        if QThread.currentThread() != self.thread():
            return QMetaObject.invokeMethod(
                self,
                "_add_stop",
                Qt.ConnectionType.BlockingQueuedConnection,
                Q_RETURN_ARG(bool),
                Q_ARG(str, address),
            )

        return self._add_stop(address)

    @Slot(str, result=bool)
    def _add_stop(self, address: str):
        place = self.get_coordinates(address)
        if place is None:
            return False

        self._stops.append({
            "label": place["address"],
            "address": place["address"],
            "lat": place["latitude"],
            "lon": place["longitude"],
        })
        self.routePointsChanged.emit()
        self.stopsChanged.emit()
        print(f"Adding stop at {address}")
        return True

    @Slot(str, result=bool)
    def remove_stop(self, address: str):
        for index, stop in enumerate(self._stops):
            if stop["address"].lower() == address.strip().lower():
                self._stops.pop(index)
                self.routePointsChanged.emit()
                self.stopsChanged.emit()
                print(f"Removing stop at {address}")
                return True
        return False

    @Slot(result=bool)
    def clear_route(self):
        self._stops.clear()
        self._destination = ""
        self._destination_coordinates = None
        self.destinationChanged.emit()
        self.routePointsChanged.emit()
        self.stopsChanged.emit()
        print("Clearing route")
        return True
