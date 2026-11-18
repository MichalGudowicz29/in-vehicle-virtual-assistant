from types import SimpleNamespace

import pytest

from session_controls import SessionControls
from session_report import SessionReport


def test_touch_executes_real_action_and_records_its_failure():
    calls = []
    car = SimpleNamespace(music=SimpleNamespace(select_track=lambda title: calls.append(title) or False))
    report = SessionReport()
    controls = SessionControls(car, report)
    assert controls.performTouch('music', 'select_track', ['Unknown']) is False
    assert calls == ['Unknown']
    events = report.snapshot()['events']
    assert [e['type'] for e in events] == ['touch_start', 'touch_end']
    assert events[-1]['success'] is False
    assert events[0]['arguments'] == ['Unknown']


def test_touch_cannot_invoke_arbitrary_attributes():
    report = SessionReport()
    controls = SessionControls(SimpleNamespace(), report)
    assert controls.performTouch('__class__', '__init__', []) is False
    assert report.snapshot()['events'][-1]['success'] is False


def test_disabled_touch_cannot_change_state_or_add_touch_measurements():
    from CarSystem.car_system import CarSystem
    car = CarSystem()
    report = SessionReport()
    controls = SessionControls(car, report, touch_enabled=False)
    assert controls.touchEnabled is False
    assert controls.performTouch('music', 'next_track', []) is False
    assert car.music.currentTrackIndex == 0
    controls.recordTouch('open_music')
    assert report.snapshot()['events'] == []
    assert car.music.next_track() is True  # Agent actions bypass touch controls.
    assert car.music.currentTrackIndex == 1


@pytest.mark.parametrize('touch_enabled', [True, False])
def test_main_qml_loads_and_touch_arguments_cross_qt_boundary(tmp_path, music_file, touch_enabled):
    import os
    import subprocess
    import sys
    script = '''
import sys
import pygame
from PySide6.QtCore import QUrl, QMetaObject, Qt, QEventLoop, QTimer, QObject
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine, QQmlComponent
from PySide6.QtQuick import QQuickItem
from threading import Event
from CarSystem.car_system import CarSystem
from shutdown import ShutdownController
from session_report import SessionReport
from session_controls import SessionControls

load = pygame.mixer.music.load
pygame.mixer.music.load = lambda _path: load(sys.argv[1])
app = QApplication([])
car = CarSystem()
report = SessionReport()
touch_enabled = sys.argv[2] == 'True'
controls = SessionControls(car, report, touch_enabled=touch_enabled)
shutdown = ShutdownController(Event(), report=report)
engine = QQmlApplicationEngine()
for name, obj in [('car', car), ('sessionControls', controls), ('shutdownController', shutdown)]:
    engine.rootContext().setContextProperty(name, obj)
engine.load('Main.qml')
assert engine.rootObjects()
assert engine.rootObjects()[0].property('contentItem').isEnabled() is touch_enabled
window = engine.rootObjects()[0]
banner = window.findChild(QQuickItem, 'userMessageBanner')
assert banner is not None and not banner.isVisible()
controls.showUserMessage('Nie ukończono polecenia. Sprawdź stan wykonanych czynności.')
app.processEvents()
assert banner.isVisible() and banner.width() > 0 and banner.height() > 0
label = banner.findChild(QQuickItem, 'userMessageText')
assert label.property('text') == 'Nie ukończono polecenia. Sprawdź stan wykonanych czynności.'
controls.showUserMessage('')
app.processEvents()
assert not banner.isVisible()
controls.showUserMessage('Powtórz polecenie.')
app.processEvents()
if touch_enabled:
    dismiss = banner.findChild(QQuickItem, 'dismissUserMessage')
    assert dismiss.isEnabled()
    assert QMetaObject.invokeMethod(dismiss, 'clicked', Qt.DirectConnection)
    app.processEvents()
    assert not banner.isVisible()
controls.showUserMessage('Powtórz polecenie.')
timer = window.findChild(QObject, 'userMessageTimer')
assert timer.property('running')
timer.setProperty('interval', 1)
loop = QEventLoop()
QTimer.singleShot(30, loop.quit)
loop.exec()
assert not banner.isVisible()
component = QQmlComponent(engine)
component.setData(b'import QtQuick; QtObject { property bool accepted: sessionControls.performTouch("contacts", "call_contact", ["Anna Kowalska", "work"]) }', QUrl())
assert not component.isError(), [e.toString() for e in component.errors()]
obj = component.create()
assert obj is not None and obj.property('accepted') is touch_enabled
assert car.contacts.currentContactName == ('Anna Kowalska' if touch_enabled else '')
assert any(e['type'] == 'touch_end' and e['success'] for e in report.events) is touch_enabled
assert any(e['type'] == 'screen_change' and e['screen'] == 'home' for e in report.events)
print('QML and QVariantList: OK')
'''
    result = subprocess.run([sys.executable, '-c', script, str(music_file), str(touch_enabled)], env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen', 'SDL_AUDIODRIVER': 'dummy'}, text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'QML and QVariantList: OK' in result.stdout
