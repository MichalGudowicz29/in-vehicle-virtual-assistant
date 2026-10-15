import unittest

from typing import cast

from CarSystem.car_system import CarSystem
from CarSystem.music_controller import MusicController
from CarSystem.navigation_controller import NavigationController


class CarSystemTests(unittest.TestCase):
    def test_set_destination_updates_qml_property(self):
        car = CarSystem()
        navigation = cast(NavigationController, car.navigation)

        navigation.set_destination("ul. Końcowa 5, Szczecin")

        self.assertEqual(navigation.destination, "ul. Końcowa 5, Szczecin")

    def test_navigation_builds_route_points_from_hardcoded_places(self):
        car = CarSystem()
        navigation = cast(NavigationController, car.navigation)

        navigation.set_destination("ul. Końcowa 5, Szczecin")
        navigation.add_stop("ul. Stacyjna 10, Szczecin")

        self.assertEqual(
            [point["address"] for point in navigation.routePoints],
            [
                "ul. Startowa 1, Szczecin",
                "ul. Stacyjna 10, Szczecin",
                "ul. Końcowa 5, Szczecin",
            ],
        )

    def test_navigation_rejects_unknown_place(self):
        car = CarSystem()
        navigation = cast(NavigationController, car.navigation)

        self.assertFalse(navigation.set_destination("Unknown place"))
        self.assertEqual(navigation.routePoints[0]["label"], "start")
        self.assertEqual(len(navigation.routePoints), 1)

    def test_navigation_removes_stops_and_clears_destination(self):
        car = CarSystem()
        navigation = cast(NavigationController, car.navigation)

        navigation.set_destination("ul. Końcowa 5, Szczecin")
        navigation.add_stop("ul. Stacyjna 10, Szczecin")

        self.assertTrue(navigation.remove_stop("ul. Stacyjna 10, Szczecin"))
        self.assertEqual(
            [point["address"] for point in navigation.routePoints],
            ["ul. Startowa 1, Szczecin", "ul. Końcowa 5, Szczecin"],
        )

        navigation.clear_route()

        self.assertEqual(navigation.destination, "")
        self.assertEqual(
            [point["address"] for point in navigation.routePoints],
            ["ul. Startowa 1, Szczecin"],
        )
        
    def test_play_pause_toggles_playing_state(self):
        car = CarSystem()
        music = cast(MusicController, car.music)

        self.assertFalse(music.isPlaying)

        music.play_pause()
        self.assertTrue(music.isPlaying)

        music.play_pause()
        self.assertFalse(music.isPlaying)

    def test_next_track_reports_playing_state(self):
        car = CarSystem()
        music = cast(MusicController, car.music)

        music.next_track()

        self.assertTrue(music.isPlaying)

    def test_selecting_unknown_track_reports_failure(self):
        car = CarSystem()
        music = cast(MusicController, car.music)

        self.assertFalse(music.select_track("Unknown track"))


if __name__ == "__main__":
    unittest.main()
