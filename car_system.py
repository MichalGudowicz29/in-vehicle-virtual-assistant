class CarSystem:
    def play_pause(self): print("Play/Pause")
    def next_track(self): print("Next track")
    def previous_track(self): print("Previous track")
    def seek(self, seconds: int): print(f"Seek {seconds} seconds")

    def find_contact(self, name: str): print(f"Find contact {name}")
    def call_contact(self, name: str, number_type: str | None = None): print(f"Call contact {name} with number type {number_type}")

    def set_destination(self, address: str): print(f"Set destination to {address}")
    def save_address(self, label: str, address: str): print(f"Save address {label}: {address}")