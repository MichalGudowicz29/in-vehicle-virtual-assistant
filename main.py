import sys

from PySide6.QtCore import QThread
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine

from car_system import CarSystem
from qml_backend import QmlBackend
from voice_worker import VoiceWorker

app = QApplication(sys.argv)

car = CarSystem()
backend = QmlBackend(car)

#utworzenie wątku dla VoiceWorker
assistant_thread = QThread()

#startowanie VoiceWorker w osobnym wątku
voice_worker = VoiceWorker(car)

#przeniesienie VoiceWorker do osobnego wątku
voice_worker.moveToThread(assistant_thread)
print("Moving voice worker to assistant thread")

assistant_thread.started.connect(voice_worker.run)

engine = QQmlApplicationEngine()
engine.rootContext().setContextProperty("backend", backend)
engine.load("Main.qml")
print("Loaded QML engine...")

if not engine.rootObjects():
    print("Failed to load QML engine.")
    sys.exit(-1)

print("Starting assistant thread...")

assistant_thread.start()
print("Assistant thread started")

exit_code = app.exec()

assistant_thread.quit()
assistant_thread.wait()

print("Application exiting")
sys.exit(exit_code)

