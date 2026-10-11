import sys
import argparse

from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine

from car_system import CarSystem
from qml_backend import QmlBackend
from assistant import Assistant
from asr import listen

app = QApplication(sys.argv)

car = CarSystem()
backend = QmlBackend(car)
assistant = Assistant(car)


#parse starting arguments to choose 
parser = argparse.ArgumentParser(description="Car system application")
parser.add_argument("--mode", choices=["qml", "assistant"], default="qml", help="Mode to run the application in")
args = parser.parse_args()
mode = args.mode


if mode == "qml":
    #QML start
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("backend", backend)
    engine.load("Main.qml")
    
    if not engine.rootObjects():
        sys.exit(-1)
        
    sys.exit(app.exec())

if mode == "assistant":
    while True:
        text = listen()

        if text is None:
            break

        if text:
            print(f"Rozpoznano: {text}")
            response = assistant.handle_text(text)
            print(response)

