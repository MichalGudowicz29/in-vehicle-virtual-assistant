from typing import cast

from CarSystem.car_system import CarSystem
from CarSystem.navigation_controller import NavigationController


def test_background_music_action_returns_its_real_failure(qt_call):
    car = CarSystem()

    success = qt_call(
        lambda: car.music.select_track("Unknown track")
    )

    assert success is False


def test_background_contact_action_returns_its_real_failure(qt_call):
    car = CarSystem()

    success = qt_call(
        lambda: car.contacts.call_contact("Robert Lewandowski", "work")
    )

    assert success is False


def test_background_navigation_action_returns_its_real_failure(qt_call):
    car = CarSystem()
    navigation = cast(NavigationController, car.navigation)

    success = qt_call(
        lambda: navigation.set_destination("Unknown place")
    )

    assert success is False
