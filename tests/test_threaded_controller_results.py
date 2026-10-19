import threading
import time

from PySide6.QtCore import QCoreApplication

from CarSystem.car_system import CarSystem


def _call_from_background(action):
    app = QCoreApplication.instance() or QCoreApplication([])
    result = {}

    def run_action():
        result["value"] = action()

    worker = threading.Thread(target=run_action)
    worker.start()

    deadline = time.monotonic() + 1
    while worker.is_alive() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.001)

    worker.join(timeout=0.1)
    assert not worker.is_alive(), "Controller call did not finish."
    return result["value"]


def test_background_music_action_returns_its_real_failure():
    car = CarSystem()

    success = _call_from_background(
        lambda: car.music.select_track("Unknown track")
    )

    assert success is False


def test_background_contact_action_returns_its_real_failure():
    car = CarSystem()

    success = _call_from_background(
        lambda: car.contacts.call_contact("Robert Lewandowski", "work")
    )

    assert success is False


def test_background_navigation_action_returns_its_real_failure():
    car = CarSystem()

    success = _call_from_background(
        lambda: car.navigation.set_destination("Unknown place")
    )

    assert success is False
