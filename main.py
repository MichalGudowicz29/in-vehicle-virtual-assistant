import sys

from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine

from car_system import CarSystem
from qml_backend import QmlBackend
from assistant import Assistant

app = QApplication(sys.argv)

car = CarSystem()
backend = QmlBackend(car)
assistant = Assistant(car)

#QML start
engine = QQmlApplicationEngine()
engine.rootContext().setContextProperty("backend", backend)
engine.load("Main.qml")


#Assistant start
while True:
    text = input("> ")
    response = assistant.handle_text(text)
    print(response)

if not engine.rootObjects():
    sys.exit(-1)

sys.exit(app.exec())