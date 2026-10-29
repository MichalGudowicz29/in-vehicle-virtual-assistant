import os
import sys
import signal
import argparse
from pathlib import Path

os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")

from PySide6.QtCore import QThread, QTimer, Qt
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine

from CarSystem.car_system import CarSystem
from voice_worker import VoiceWorker
from shutdown import ShutdownController
from session_report import SessionReport
from session_controls import SessionControls

parser = argparse.ArgumentParser(description="Asystent samochodowy: mikrofon lub jedna tura z pliku audio.")
parser.add_argument("--audio-file", type=Path, help="Plik audio podawany do ASR w naturalnym tempie.")
args, qt_args = parser.parse_known_args()
if args.audio_file is not None:
    args.audio_file = args.audio_file.expanduser().resolve()
    if not args.audio_file.is_file():
        parser.error(f"Nie znaleziono pliku audio: {args.audio_file}")

app = QApplication([sys.argv[0], *qt_args])
app.setQuitOnLastWindowClosed(False)

session_report = SessionReport(audio_file=args.audio_file)
car = CarSystem()
session_controls = SessionControls(car, session_report)

#utworzenie wątku dla VoiceWorker
assistant_thread = QThread()

#startowanie VoiceWorker w osobnym wątku
voice_worker = VoiceWorker(car, report=session_report, audio_file=args.audio_file)
shutdown_controller = ShutdownController(voice_worker.stop_event, report=session_report)

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
engine.rootContext().setContextProperty("sessionControls", session_controls)
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
