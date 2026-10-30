"""Load the real map without a tile server or routing service."""
import os
import subprocess
import sys


def test_map_updates_route_without_network(music_file):
    script = r'''
import sys
import pygame
from PySide6.QtCore import QUrl, QObject
from PySide6.QtGui import QGuiApplication
from PySide6.QtTest import QTest
from PySide6.QtNetwork import QNetworkAccessManager
from PySide6.QtQml import QQmlNetworkAccessManagerFactory
from PySide6.QtQuick import QQuickView
from CarSystem.car_system import CarSystem

app = QGuiApplication([])
load = pygame.mixer.music.load
pygame.mixer.music.load = lambda _: load(sys.argv[1])
requests = []
class Manager(QNetworkAccessManager):
    def createRequest(self, operation, request, outgoing=None):
        requests.append(request.url().toString())
        return super().createRequest(operation, request, outgoing)
class Factory(QQmlNetworkAccessManagerFactory):
    def create(self, parent):
        return Manager(parent)
factory = Factory()
car = CarSystem()
view = QQuickView()
view.engine().setNetworkAccessManagerFactory(factory)
view.rootContext().setContextProperty('car', car)
view.setResizeMode(QQuickView.SizeRootObjectToView)
view.resize(1280, 720)
view.setSource(QUrl.fromLocalFile(str(__import__('pathlib').Path('qml/MapScreen.qml').resolve())))
assert view.status() == QQuickView.Ready, view.errors()
view.show()
root = view.rootObject()
def labels():
    QTest.qWait(50)
    repeater = root.findChild(QObject, 'routeMarkers')
    assert repeater is not None, 'Map must display local route markers'
    markers = [item for item in repeater.parentItem().childItems()
               if item.property('index') is not None]
    return [item.property('text') for item in sorted(markers, key=lambda item: item.property('index'))]
assert labels() == ['START']
assert car.navigation.set_destination('ul. Żołnierska 47, Szczecin')
assert labels() == ['START', '1']
assert car.navigation.add_stop('ul. Stacyjna 10, Szczecin')
assert labels() == ['START', '1', '2']
assert car.navigation.add_stop('ul. Stacyjna 10, Szczecin')
assert labels() == ['START', '1', '2', '3']
assert car.navigation.remove_stop('ul. Stacyjna 10, Szczecin')
assert labels() == ['START', '1', '2']
view.resize(1000, 600)
assert labels() == ['START', '1', '2']
assert car.navigation.clear_route()
assert labels() == ['START']
assert requests == [], requests
view.setSource(QUrl())
'''
    result = subprocess.run(
        [sys.executable, '-c', script, str(music_file)],
        env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen', 'QT_QUICK_CONTROLS_STYLE': 'Basic'},
        capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'ReferenceError' not in result.stderr
    assert 'TypeError' not in result.stderr
