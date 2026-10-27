import os
import sys
import signal

os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")

from PySide6.QtCore import QThread, QTimer, Qt
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine

from CarSystem.car_system import CarSystem
from voice_worker import VoiceWorker
from shutdown import ShutdownController

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)

car = CarSystem()

#utworzenie wątku dla VoiceWorker
assistant_thread = QThread()

#startowanie VoiceWorker w osobnym wątku
voice_worker = VoiceWorker(car)
shutdown_controller = ShutdownController(voice_worker.stop_event)

#przeniesienie VoiceWorker do osobnego wątku
voice_worker.moveToThread(assistant_thread)
print("Moving voice worker to assistant thread")

assistant_thread.started.connect(voice_worker.run)
voice_worker.finished.connect(assistant_thread.quit, Qt.ConnectionType.DirectConnection)
assistant_thread.finished.connect(shutdown_controller.finish)
shutdown_controller.finished.connect(app.quit)

# Timer pozwala Pythonowi odebrać Ctrl+C podczas działania pętli Qt.
signal_timer = QTimer()
signal_timer.timeout.connect(lambda: None)
signal_timer.start(100)
signal.signal(signal.SIGINT, lambda *_: shutdown_controller.request_shutdown())

engine = QQmlApplicationEngine()
engine.rootContext().setContextProperty("car", car)
engine.rootContext().setContextProperty("shutdownController", shutdown_controller)
engine.load("Main.qml")
print("Loaded QML engine...")

if not engine.rootObjects():
    print("Failed to load QML engine.")
    sys.exit(-1)

print("Starting assistant thread...")

assistant_thread.start()
print("Assistant thread started")

exit_code = app.exec()

assistant_thread.wait()

print("Application exiting")
sys.exit(exit_code)
