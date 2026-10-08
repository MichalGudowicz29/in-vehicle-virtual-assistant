from dotenv import load_dotenv
from langchain.core import 



class Assistant:
    def __init__(self, car):
        self.car = car

    
    def handle_text(self, text: str):
        text = text.lower()

        if "muzyka" in text or "play" in text:
            self.car.play_pause()
            return "Włączam lub pauzuję muzykę."

        if "następny" in text or "next" in text:
            self.car.next_track()
            return "Przełączam na następny utwór."

        if "zadzwoń do marcina" in text:
            self.car.call_contact("Marcin")
            return "Dzwonię do Marcina."

        if "nawiguj" in text:
            address = text.replace("nawiguj do", "").strip()
            self.car.set_destination(address)
            return f"Ustawiam cel: {address}"

        return "Nie rozumiem polecenia."