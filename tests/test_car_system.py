import unittest

from car_system import CarSystem


class CarSystemTests(unittest.TestCase):
    def test_set_destination_updates_qml_property(self):
        car = CarSystem()

        car.set_destination("Szczecin")

        self.assertEqual(car.destination, "Szczecin")
        
    def test_play_pause_toggles_playing_state(self):
        car = CarSystem()

        self.assertFalse(car.isPlaying)

        car.play_pause()
        self.assertTrue(car.isPlaying)

        car.play_pause()
        self.assertFalse(car.isPlaying)


if __name__ == "__main__":
    unittest.main()
