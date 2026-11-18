"""Entry point: Qt GUI (touch) + background voice worker (ASR → LLM → TTS) + session report.

Modes:
  python main.py                         microphone, touch enabled
  python main.py --audio-file X.mp3      one voice turn from a file, then exit
  python main.py --experiment --audio-file X.mp3
                                         runner trial: no touch/mic, music starts on
                                         "Chill song", report checkpoint every 5 s
"""

import argparse
import os
import signal
import sys
from pathlib import Path

os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
os.environ["QT_IM_MODULE"] = "qtvirtualkeyboard"
os.environ["QT_VIRTUALKEYBOARD_DESKTOP_DISABLE"] = "1"

from PySide6.QtCore import QThread, QTimer, Qt
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication

import config
from asr import ASR_MODELS, resolve_model
from CarSystem.car_system import CarSystem
from session_controls import SessionControls
from session_report import SessionReport
from shutdown import ShutdownController
from voice_worker import VoiceWorker


def parse_args():
    parser = argparse.ArgumentParser(description="Asystent samochodowy: mikrofon lub jedna tura z pliku audio.")
    parser.add_argument("--audio-file", type=Path, help="Plik audio podawany do ASR w naturalnym tempie.")
    parser.add_argument("--experiment", action="store_true",
                        help="Tryb runnera: wyłącznie plik audio, bez obsługi dotykowej.")
    parser.add_argument("--asr", choices=ASR_MODELS,
                        help="Model ASR (domyślnie whisper-small; w --experiment: ASR_MODEL z .env).")
    parser.add_argument("--report-dir", type=Path, default=Path("logs/sessions"),
                        help="Folder raportów TXT i JSON (domyślnie: logs/sessions).")
    args, qt_args = parser.parse_known_args()

    if args.experiment and args.audio_file is None:
        parser.error("Tryb --experiment wymaga --audio-file; mikrofon jest wyłączony.")
    if not args.experiment and config.LLM_GENERATION['reasoning'] is None:
        config.LLM_GENERATION['reasoning'] = False   # manual use: no thinking unless set in .env
    try:
        # The runner controls ASR through .env; manual use defaults to Whisper small.
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
    return args, qt_args


def start_report_checkpoints(report, directory):
    """Experiment mode: a killed trial (timeout) still leaves a partial report."""
    def save_checkpoint():
        try:
            report.save(directory, final=False)
        except Exception as error:
            print(f"Nie udało się zapisać raportu cząstkowego: {error}", file=sys.stderr, flush=True)

    save_checkpoint()
    timer = QTimer()
    timer.timeout.connect(save_checkpoint)
    timer.start(5000)
    return timer


def main():
    args, qt_args = parse_args()
    app = QApplication([sys.argv[0], *qt_args])
    app.setQuitOnLastWindowClosed(False)

    report = SessionReport(audio_file=args.audio_file, asr_model=args.asr)
    checkpoint_timer = start_report_checkpoints(report, args.report_dir) if args.experiment else None

    # Model: simulated head unit shared by touch and voice.
    car = CarSystem(initial_music_track_index=1 if args.experiment else 0)
    session_controls = SessionControls(car, report, touch_enabled=not args.experiment)

    # Voice loop in a background thread.
    voice_worker = VoiceWorker(car, report, audio_file=args.audio_file, asr=args.asr)
    voice_worker.userMessage.connect(session_controls.showUserMessage)
    assistant_thread = QThread()
    voice_worker.moveToThread(assistant_thread)
    assistant_thread.started.connect(voice_worker.run)
    voice_worker.finished.connect(assistant_thread.quit, Qt.ConnectionType.DirectConnection)

    # Shutdown: worker finishes → report saved → app quits.
    shutdown_controller = ShutdownController(voice_worker.stop_event, report,
                                             report_directory=args.report_dir, car=car)
    if checkpoint_timer is not None:
        shutdown_controller.finished.connect(checkpoint_timer.stop)
    assistant_thread.finished.connect(shutdown_controller.finish)
    shutdown_controller.finished.connect(app.quit)

    # The timer lets Python handle Ctrl+C while the Qt loop runs.
    signal_timer = QTimer()
    signal_timer.timeout.connect(lambda: None)
    signal_timer.start(100)
    signal.signal(signal.SIGINT, lambda *_: shutdown_controller.request_shutdown())

    # View: QML screens bound to the same objects.
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("car", car)
    engine.rootContext().setContextProperty("sessionControls", session_controls)
    engine.rootContext().setContextProperty("shutdownController", shutdown_controller)
    engine.load("Main.qml")
    if not engine.rootObjects():
        print("Failed to load QML engine.")
        sys.exit(-1)

    print(f"ASR: {args.asr}", flush=True)
    assistant_thread.start()
    exit_code = app.exec()
    assistant_thread.wait()
    print("Application exiting")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
