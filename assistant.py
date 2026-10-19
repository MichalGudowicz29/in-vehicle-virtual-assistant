import os
import time
from operator import index

from distro import name
from dotenv import load_dotenv # type: ignore

from langchain.agents import create_agent # type: ignore
from langchain_core.runnables import RunnableConfig
from langchain.tools import tool # type: ignore
from langgraph.checkpoint.memory import InMemorySaver

from typing import Any, Literal
from langchain.messages import HumanMessage
from langchain.agents.middleware.types import InputAgentState
from graph import build_graph


load_dotenv()


SYSTEM_PROMPT_SHORT = """
Jesteś asystentem głosowym samochodu. Twoim zadaniem jest wykonywanie
poleceń użytkownika za pomocą dostępnych narzędzi HMI.

Zasady:
- Bezpieczeństwo i spokój kierowcy są najważniejsze.
- Wykonuj polecenia bez zbędnych pytań, jeśli ich intencja jest jasna.
- Nigdy nie zgaduj istotnych informacji. Jeśli brakuje danych lub
  istnieje istotna niejednoznaczność, zadaj jedno krótkie pytanie.
- Zasada dotycząca połączeń: najpierw użyj get_contacts. Jeśli wybrany
  kontakt ma więcej niż jeden numer, a użytkownik nie podał typu numeru,
  NIE wywołuj call_contact. Zapytaj dokładnie: „Czy wybrać numer mobilny
  czy służbowy?”. Dopiero po odpowiedzi wywołaj call_contact jeden raz,
  używając number_type="mobile" albo number_type="work".
- Nigdy nie próbuj kolejno obu numerów i nie wywołuj call_contact dwa razy
  dla jednego polecenia użytkownika.
- Korzystaj wyłącznie z dostępnych narzędzi i nie deklaruj sukcesu
  bez potwierdzenia wykonania operacji.
- Wykonuj tylko żądane czynności. Nie rozpraszaj kierowcy.
- W przypadku błędu poinformuj krótko o problemie. Niebezpieczne
  polecenia odrzuć lub bezpiecznie odrocz.
"""


class Assistant:
    def __init__(self, car, thread_id: str = "user_session_1"):
        self.car = car
        self.checkpointer = InMemorySaver()
        self.thread_config: RunnableConfig = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": 8,
        }
        self.graph = build_graph(car)
        self.execution_events: list[dict[str, Any]] = []
        self.agent = self.initialize_agent()

    def _execute_graph_action(self, intent: str, action: str, payload: dict):
        if not hasattr(self, "execution_events"):
            self.execution_events = []

        started_at = time.perf_counter_ns()
        self.execution_events.append({
            "type": "graph_action_started",
            "intent": intent,
            "action": action,
            "payload": payload,
            "time_ns": started_at,
        })

        try:
            state = self.graph.invoke({
                "intent": intent,
                "action": action,
                "payload": payload,
            })
        except Exception as error:
            finished_at = time.perf_counter_ns()
            self.execution_events.append({
                "type": "graph_action_failed",
                "intent": intent,
                "action": action,
                "error_type": type(error).__name__,
                "error_message": str(error),
                "duration_ms": (finished_at - started_at) / 1_000_000,
                "time_ns": finished_at,
            })
            raise

        result = state["result"]
        finished_at = time.perf_counter_ns()
        self.execution_events.append({
            "type": "graph_action_finished",
            "intent": intent,
            "action": action,
            "success": result.get("success", False),
            "result": result,
            "duration_ms": (finished_at - started_at) / 1_000_000,
            "time_ns": finished_at,
        })
        return result
        
    def build_tools(self):
        car = self.car

        # Muzyka
        @tool
        def play_pause():
            """Włącza lub pauzuje muzykę."""
            return self._execute_graph_action("music", "play_pause", {})

        @tool
        def next_track():
            """Przełącza na następny utwór."""
            return self._execute_graph_action("music", "next_track", {})
            
        @tool
        def previous_track():
            """Przełącza na poprzedni utwór."""
            return self._execute_graph_action("music", "previous_track", {})

            
        
        @tool
        def get_track_list():
            """Zwraca listę dostępnych utworów."""
            tracks = car.music.tracks

            return {
                "success": True,
                "tracks": [
                    {
                        "id": index,
                        "title": track["title"],
                        "author": track["artist"],
                    }
                    for index, track in enumerate(tracks)
                ],
                "message": "Retrieved track list successfully.",
            }
            
        @tool
        def search_track(query: str):
            """Wyszukuje utwory po tytule lub wykonawcy."""
            query = query.lower()
            tracks = car.music.tracks

            matches = [
                {
                    "id": index,
                    "title": track["title"],
                    "author": track["artist"],
                }
                for index, track in enumerate(tracks)
                if query in track["title"].lower()
                or query in track["artist"].lower()
            ]

            return {
                "success": bool(matches),
                "tracks": matches,
                "message": (
                    f"Found {len(matches)} matching tracks."
                    if matches
                    else "No tracks found."
                ),
            }
        
        @tool
        def select_track(title: str):
            """Wybiera utwór na podstawie tytułu."""
            return self._execute_graph_action(
                "music",
                "select_track",
                {"title": title},
            )

        # Kontakty
        @tool
        def get_contacts():
            """Zwraca wszystkich zapisanych kontaktów wraz ze wszystkimi numerami."""

            contacts = [
                {
                    "id": index,
                    "name": contact["name"],
                    "numbers": {
                        key: value
                        for key, value in contact.items()
                        if key != "name"
                    },
                }
                for index, contact in enumerate(car.contacts.contacts)
            ]

            return {
                "success": bool(contacts),
                "contacts": contacts,
                "message": "Lista kontaktów została pobrana.",
            }
        
        @tool
        def call_contact(
            name: str,
            number_type: Literal["mobile", "work"],
        ):
            """Inicjuje połączenie z kontaktem o podanej nazwie i typie numeru."""
            return self._execute_graph_action(
                "contacts",
                "call_contact",
                {
                    "name": name,
                    "number_type": number_type,
                },
            )
    
        # Nawigacja
        @tool
        def navigate_to(street: str, city: str, number: str):
            """Ustawia cel nawigacji na podany adres. street, city i number muszą być podane."""
            address = f"ul. {street} {number}, {city}"
            return self._execute_graph_action(
                "navigation",
                "set_destination",
                {"address": address},
            )
            
        @tool
        def add_stop(street: str, city: str, number: str):
            """Dodaje przystanek do trasy na podany adres. street, city i number muszą być podane."""
            address = f"ul. {street} {number}, {city}"
            return self._execute_graph_action(
                "navigation",
                "add_stop",
                {"address": address},
            )
        
        @tool 
        def get_places_list():
            """Zwraca listę dostępnych miejsc, ktore mozna dodac jako przystanek."""
            return {
                "success": True,
                "places": car.navigation.places_list,
                "message": "Retrieved places list successfully.",
            }   
            

        return [
            # Muzyka
            play_pause, 
            next_track, 
            previous_track, 
            search_track, 
            select_track,
            get_track_list,
            
            # Kontakty
            call_contact, 
            get_contacts,
            
            # Nawigacja
            navigate_to, 
            add_stop,
            get_places_list,
        ]


    # dodac try except 
    def initialize_agent(self):
        return create_agent(
            model="openai:gpt-4o-mini",
            system_prompt=SYSTEM_PROMPT_SHORT,
            tools=self.build_tools(),
            checkpointer=self.checkpointer,
        )
    
    
    # dodac try except 
    def handle_text(self, text: str):
        input_data: InputAgentState = {
            "messages": [
                {
                    "role": "user",
                    "content": text,
                }
            ]
        }

        final_text = ""

        for raw_chunk in self.agent.stream(
            input_data,
            config=self.thread_config,
            stream_mode="updates",
            version="v2",
        ):
            if not isinstance(raw_chunk, dict):
                continue

            data = raw_chunk.get("data")
            if not isinstance(data, dict):
                continue

            for node_name, raw_update in data.items():
                print(f"\n--- node: {node_name} ---")

                if not isinstance(raw_update, dict):
                    continue

                messages = raw_update.get("messages", [])
                if not isinstance(messages, list):
                    continue

                for message in messages:
                    content = getattr(message, "content", "")
                    print(f"type: {type(message).__name__}")
                    print(f"content: {content}")

                    tool_calls = getattr(message, "tool_calls", None)
                    if tool_calls:
                        print(f"tool calls: {tool_calls}")

                    if isinstance(content, str) and content:
                        final_text = content

        return final_text
