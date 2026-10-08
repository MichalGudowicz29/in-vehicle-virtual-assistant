from dotenv import load_dotenv

from langchain.agents import create_agent
from langchain.tools import tool

load_dotenv()

class Assistant:
    def __init__(self, car):
        self.car = car
        self.agent = self.initialize_agent()
        
    def build_tools(self):
        car = self.car

        @tool
        def play_pause() -> str:
            """Włącza lub pauzuje muzykę."""
            car.play_pause()

        @tool
        def next_track() -> str:
            """Przełącza na następny utwór."""
            car.next_track()
            
        @tool
        def previous_track() -> str:
            """Przełącza na poprzedni utwór."""
            car.previous_track()

        @tool
        def call_contact(name: str, number_type: str) -> str:
            """Dzwoni do kontaktu o podanej nazwie."""
            car.call_contact(name)

        @tool
        def navigate_to(address: str) -> str:
            """Ustawia cel nawigacji na podany adres."""
            car.set_destination(address)
            
        @tool
        def save_address(label: str, address: str) -> str:
            """Zapisuje adres pod podaną etykietą."""
            car.save_address(label, address)

        return [play_pause, next_track, previous_track, call_contact, navigate_to]

    
    def initialize_agent(self):
        return create_agent(
            model="openai:gpt-4o-mini",
            tools=self.build_tools(),
        )
    
    def handle_text(self, text: str):
        result = self.agent.invoke({
            "messages": [
                {"role": "user", "content": text}
            ]
        })

        return result["messages"][-1].content