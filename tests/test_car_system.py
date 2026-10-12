import unittest

from car_system import CarSystem


class CarSystemTests(unittest.TestCase):
    def test_set_destination_updates_qml_property(self):
        car = CarSystem()

        car.set_destination("Szczecin")

        self.assertEqual(car.destination, "Szczecin")


if __name__ == "__main__":
    unittest.main()
