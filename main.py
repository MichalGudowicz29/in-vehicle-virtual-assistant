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

#połączenie sygnału started wątku z metodą run VoiceWorker
assistant_thread.started.connect(voice_worker.run)

engine = QQmlApplicationEngine()
engine.rootContext().setContextProperty("backend", backend)
engine.load("Main.qml")

if not engine.rootObjects():
    sys.exit(-1)

assistant_thread.start()
exit_code = app.exec()

assistant_thread.quit()
assistant_thread.wait()
sys.exit(exit_code)

