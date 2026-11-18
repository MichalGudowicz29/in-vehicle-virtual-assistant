import os
import sys
import signal
import argparse
from pathlib import Path

os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
os.environ["QT_IM_MODULE"] = "qtvirtualkeyboard"
os.environ["QT_VIRTUALKEYBOARD_DESKTOP_DISABLE"] = "1"

from PySide6.QtCore import QThread, QTimer, Qt
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine

from CarSystem.car_system import CarSystem
from voice_worker import VoiceWorker
from shutdown import ShutdownController
from session_report import SessionReport
from session_controls import SessionControls
from asr import ASR_MODELS, resolve_model
import config

parser = argparse.ArgumentParser(description="Asystent samochodowy: mikrofon lub jedna tura z pliku audio.")
parser.add_argument("--audio-file", type=Path, help="Plik audio podawany do ASR w naturalnym tempie.")
parser.add_argument("--experiment", action="store_true",
                    help="Tryb runnera: wyłącznie plik audio, bez obsługi dotykowej.")
parser.add_argument("--asr", choices=ASR_MODELS,
                    help="Model ASR (domyślnie whisper-small; w --experiment: ASR_MODEL z .env).")
parser.add_argument("--report-dir", type=Path, default=Path("logs/sessions"),
                    help="Folder raportów TXT i JSON (domyślnie: logs/sessions).")
args, qt_args = parser.parse_known_args()
if not args.experiment and config.LLM_GENERATION['reasoning'] is None:
    config.LLM_GENERATION['reasoning'] = False
if args.experiment and args.audio_file is None:
    parser.error("Tryb --experiment wymaga --audio-file; mikrofon jest wyłączony.")
try:
    args.asr = resolve_model(args.asr if args.asr is not None or args.experiment else "whisper-small")
except ValueError as error:
    parser.error(str(error))
if args.audio_file is not None:
    args.audio_file = args.audio_file.expanduser().resolve()
    if not args.audio_file.is_file():
        parser.error(f"Nie znaleziono pliku audio: {args.audio_file}")
args.report_dir = args.report_dir.expanduser().resolve()
try:
    args.report_dir.mkdir(parents=True, exist_ok=True)
except OSError as error:
    parser.error(f"Nie można przygotować folderu raportów {args.report_dir}: {error}")

app = QApplication([sys.argv[0], *qt_args])
app.setQuitOnLastWindowClosed(False)

session_report = SessionReport(audio_file=args.audio_file, asr_model=args.asr)
checkpoint_timer = None
if args.experiment:
    def save_checkpoint():
        try:
            session_report.save(args.report_dir, final=False)
        except Exception as error:
            print(f"Nie udało się zapisać raportu cząstkowego: {error}", file=sys.stderr, flush=True)

    save_checkpoint()
    checkpoint_timer = QTimer()
    checkpoint_timer.timeout.connect(save_checkpoint)
    checkpoint_timer.start(5000)
car = CarSystem(initial_music_track_index=1 if args.experiment else 0)
session_controls = SessionControls(car, session_report, touch_enabled=not args.experiment)

#utworzenie wątku dla VoiceWorker
assistant_thread = QThread()

#startowanie VoiceWorker w osobnym wątku
voice_worker = VoiceWorker(car, report=session_report, audio_file=args.audio_file, asr=args.asr)
voice_worker.userMessage.connect(session_controls.showUserMessage)
shutdown_controller = ShutdownController(voice_worker.stop_event, report=session_report,
                                         report_directory=args.report_dir, car=car)
if checkpoint_timer is not None:
    shutdown_controller.finished.connect(checkpoint_timer.stop)

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

print(f"ASR: {args.asr}", flush=True)
print("Starting assistant thread...")

assistant_thread.start()
print("Assistant thread started")

exit_code = app.exec()

assistant_thread.wait()

print("Application exiting")
sys.exit(exit_code)
