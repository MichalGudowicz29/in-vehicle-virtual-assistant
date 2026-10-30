"""Exercise the real Qt keyboard and both forms without voice or model downloads."""
import os
import subprocess
import sys


def test_keyboard_opens_types_and_closes_on_enter_and_actions(music_file):
    script = r'''
import sys
from threading import Event
import pygame
from PySide6.QtCore import Qt, QMetaObject, QObject, QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow
from PySide6.QtTest import QTest
from CarSystem.car_system import CarSystem
from session_report import SessionReport
from session_controls import SessionControls
from shutdown import ShutdownController

app = QApplication([])
load = pygame.mixer.music.load
pygame.mixer.music.load = lambda _: load(sys.argv[1])
car = CarSystem()
report = SessionReport()
controls = SessionControls(car, report)
shutdown = ShutdownController(Event(), report)
engine = QQmlApplicationEngine()
engine.rootContext().setContextProperty('car', car)
engine.rootContext().setContextProperty('sessionControls', controls)
engine.rootContext().setContextProperty('shutdownController', shutdown)
engine.load('Main.qml')
assert engine.rootObjects()
window = engine.rootObjects()[0]
def settle():
    QTest.qWait(450)
def items(item=None):
    item = item or window.contentItem()
    yield item
    for child in item.childItems():
        yield from items(child)
def find(**props):
    return next(i for i in items() if i.isVisible() and all(i.property(k) == v for k, v in props.items()))
def click(item):
    p = item.mapToScene(item.boundingRect().center()).toPoint()
    QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, p)
    settle()
settle()
keyboard = window.findChild(QObject, 'screenKeyboard')
assert keyboard is not None, 'Application needs an embedded keyboard'
assert not app.inputMethod().isVisible()
home = window.findChild(QObject, 'home')
QMetaObject.invokeMethod(home, 'navigationClicked')
settle()
field = find(placeholderText='ul. Żołnierska 47, Szczecin')
click(field)
assert app.inputMethod().isVisible()
assert keyboard.property('active')
assert field.mapToScene(field.boundingRect().bottomRight()).y() <= keyboard.property('y')
# A real on-screen key must edit the focused field without stealing focus.
key = find(key=int(Qt.Key_A))
click(key)
assert field.property('text').lower() == 'a'
click(find(key=int(Qt.Key_Return)))
assert not app.inputMethod().isVisible()
assert car.navigation.destination == ''
# Reopening the same field must work after Enter.
click(field)
assert app.inputMethod().isVisible()
field.setProperty('text', 'zolnierska47')
settle()
click(find(text='ul. Żołnierska 47, Szczecin', focusPolicy=int(Qt.NoFocus), checkable=False))
assert field.property('text') == 'ul. Żołnierska 47, Szczecin'
assert car.navigation.destination == ''
assert app.inputMethod().isVisible()
click(find(text='START NAVIGATION'))
assert not app.inputMethod().isVisible()
assert car.navigation.destination == 'ul. Żołnierska 47, Szczecin'
stop = find(placeholderText='ul. Stacyjna 10, Szczecin')
click(stop)
assert app.inputMethod().isVisible()
stop.setProperty('text', 'stac')
settle()
click(find(text='ul. Stacyjna 10, Szczecin', focusPolicy=int(Qt.NoFocus), checkable=False))
assert stop.property('text') == 'ul. Stacyjna 10, Szczecin'
assert car.navigation.stops == []
assert app.inputMethod().isVisible()
click(find(text='DODAJ'))
assert not app.inputMethod().isVisible()
assert len(car.navigation.stops) == 1
assert stop.property('text') == ''
click(stop)
assert app.inputMethod().isVisible()
QTest.keyClick(window, Qt.Key_Return)
settle()
assert not app.inputMethod().isVisible()
# Changing screens while typing dismisses the keyboard too.
click(stop)
assert app.inputMethod().isVisible()
click(find(text='BACK'))
assert not app.inputMethod().isVisible()
window.setVisible(False)
engine.deleteLater()
QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
'''
    result = subprocess.run(
        [sys.executable, '-c', script, str(music_file)],
        env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen',
             'QT_QUICK_CONTROLS_STYLE': 'Basic', 'QT_IM_MODULE': 'qtvirtualkeyboard',
             'QT_VIRTUALKEYBOARD_DESKTOP_DISABLE': '1'},
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'ReferenceError' not in result.stderr
