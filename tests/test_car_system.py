import unittest

from typing import cast

from CarSystem.car_system import CarSystem
from CarSystem.music_controller import MusicController
from CarSystem.navigation_controller import NavigationController


class CarSystemTests(unittest.TestCase):
    def test_set_destination_updates_qml_property(self):
        car = CarSystem()
        navigation = cast(NavigationController, car.navigation)

        navigation.set_destination("Szczecin")

        self.assertEqual(navigation.destination, "Szczecin")
        
    def test_play_pause_toggles_playing_state(self):
        car = CarSystem()
        music = cast(MusicController, car.music)

        self.assertFalse(music.isPlaying)

        music.play_pause()
        self.assertTrue(music.isPlaying)

        music.play_pause()
        self.assertFalse(music.isPlaying)


if __name__ == "__main__":
    unittest.main()
