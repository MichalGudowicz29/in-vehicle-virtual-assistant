from dotenv import load_dotenv # type: ignore

from langchain.agents import create_agent # type: ignore
from langchain_core.runnables import RunnableConfig
from langchain.tools import tool # type: ignore
from langgraph.checkpoint.memory import InMemorySaver

load_dotenv()

class Assistant:
    def __init__(self, car, thread_id: str = "user_session_1"):
        self.car = car
        self.checkpointer = InMemorySaver()
        self.thread_config: RunnableConfig = {
            "configurable": {"thread_id": thread_id}
        }
        self.agent = self.initialize_agent()
        
    def build_tools(self):
        car = self.car

        @tool
        def play_pause():
            """Włącza lub pauzuje muzykę."""
            car.play_pause()

        @tool
        def next_track():
            """Przełącza na następny utwór."""
            car.next_track()
            
        @tool
        def previous_track():
            """Przełącza na poprzedni utwór."""
            car.previous_track()

        @tool
        def call_contact(name: str, number_type: str):
            """Dzwoni do kontaktu o podanej nazwie."""
            car.call_contact(name)

        @tool
        def navigate_to(address: str):
            """Ustawia cel nawigacji na podany adres."""
            car.set_destination(address)
            
        @tool
        def save_address(label: str, address: str):
            """Zapisuje adres pod podaną etykietą."""
            car.save_address(label, address)

        return [play_pause, next_track, previous_track, call_contact, navigate_to, save_address]

    
    def initialize_agent(self):
        return create_agent(
            model="openai:gpt-4o-mini",
            tools=self.build_tools(),
            checkpointer=self.checkpointer,
        )
    
    
    def handle_text(self, text: str):
        result = self.agent.invoke(
            {"messages": [{"role": "user", "content": text}]},
            config=self.thread_config,
        )

        return result["messages"][-1].content
