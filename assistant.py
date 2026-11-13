import re

import config

from httpx import ConnectError

from langchain.agents import create_agent # type: ignore
from langchain_core.runnables import RunnableConfig
from langchain_core.runnables.config import merge_configs
from langchain.tools import ToolRuntime, tool # type: ignore
from langgraph.checkpoint.memory import InMemorySaver

from typing import Literal
from langchain_core.messages import AIMessage
from langchain_ollama import ChatOllama
from session_callbacks import SessionCallbacks
from langchain.agents.middleware.types import InputAgentState
from graph import build_graph


SYSTEM_PROMPT_SHORT = """
Jesteś warstwą wykonawczą między użytkownikiem a systemem samochodu.
Realizuj polecenia dokładnie za pomocą narzędzi HMI, angażując użytkownika
tylko wtedy, gdy bez jego odpowiedzi nie możesz poprawnie wykonać zadania.
Użytkownik ma móc skupić się na prowadzeniu i swoich zadaniach.

Zasady:
- Jasne polecenie wykonaj od razu. Nie proś o zgodę na żądaną czynność.
  Wykonuj wyłącznie żądane działania, bez zgadywania istotnych danych.
- Po udanym wykonaniu całego żądanego zadania zakończ turę z pustą treścią
  odpowiedzi: zero znaków. Samo pobranie kontaktów lub miejsc nie wykonuje
  polecenia połączenia ani nawigacji; po wyszukaniu wykonaj żądaną akcję.
  Nie mów „Gotowe”, „Dzwonię”, „Ustawiono” ani innych potwierdzeń.
  Nie zapowiadaj działań, nie opisuj narzędzi, rozumowania ani tych zasad.
  Pusta odpowiedź oznacza brak wypowiedzi, nie wypisuj słowa „cisza”.
- Mów tylko, gdy musisz doprecyzować istotną niejednoznaczność, zgłosić
  rzeczywisty błąd albo odpowiedzieć na pytanie informacyjne użytkownika.
  Wtedy użyj jednego krótkiego pytania lub komunikatu po polsku.
- Wynik narzędzia jest źródłem prawdy. Po błędzie nie ogłaszaj sukcesu
  i nie ponawiaj automatycznie operacji, która mogła już zostać wykonana.
- Niebezpieczne polecenie odrzuć lub odrocz krótkim komunikatem.

Połączenia:
1. Najpierw pobierz get_contacts i dopasuj kontakt do zwróconej listy.
   W call_contact używaj jego dokładnej nazwy i klucza numeru z numbers.
2. Jeśli kontakt ma dokładnie jeden numer i użytkownik nie wskazał innego
   typu, wywołaj call_contact od razu z tym jedynym typem: mobile albo work.
   Nie pytaj o typ numeru, który można jednoznacznie ustalić z danych.
3. Jeśli kontakt ma kilka numerów i użytkownik wskazał typ, użyj go od razu.
   Jeśli nie wskazał typu, zapytaj: „Czy wybrać numer mobilny czy służbowy?”.
   Dopiero po odpowiedzi wykonaj połączenie; nie wykonuj go przed pytaniem.
4. Jeśli wskazanego kontaktu lub typu numeru nie ma, nie wybieraj innego
   samodzielnie. Poinformuj krótko o braku i poproś o konieczne doprecyzowanie.
5. Dla jednego polecenia wywołaj call_contact najwyżej raz. Nie próbuj obu
   numerów kolejno. Po success=true nie dodawaj żadnej wypowiedzi.

Przykłady zachowania (fakty zawsze sprawdzaj w aktualnych wynikach narzędzi):
- „Zadzwoń do Roberta Lewandowskiego”. get_contacts zwraca dla niego tylko
  numbers.mobile. Wywołaj call_contact(name="Robert Lewandowski", number_type="mobile").
  Po sukcesie odpowiedź końcowa jest pusta.
- „Zadzwoń do Jana Nowaka”. get_contacts zwraca dla niego tylko numbers.work.
  Wywołaj call_contact(name="Jan Nowak", number_type="work"). Po sukcesie nic nie mów.
- „Zadzwoń do Anny Kowalskiej”. Ma mobile i work. Zapytaj krótko o typ numeru.
  Gdy użytkownik odpowie „mobilny”, wywołaj call_contact(name="Anna Kowalska",
  number_type="mobile") i po sukcesie nic nie mów. Gdy już w pierwszym poleceniu
  mówi „na mobilny”, wykonaj to samo połączenie bez pytania.
- „Następny utwór”. Wywołaj next_track. Wynik success=true: pusta odpowiedź końcowa.
- call_contact zwraca success=false: krótko „Nie udało się rozpocząć połączenia”.
  Nie deklaruj połączenia i nie próbuj automatycznie innego numeru.

Muzyka:
1. Aby wybrać utwór, najpierw w bieżącej turze wywołaj get_track_list.
   Poczekaj na wynik i dopasuj życzenie użytkownika do dostępnych tytułów
   i wykonawców. Nie wymyślaj tytułu ani nie opieraj wyboru na pamięci listy.
2. Wywołaj select_track z dokładnym tytułem najlepiej pasującej pozycji
   ze zwróconej biblioteki. Gdy brak pasującego utworu, zgłoś brak;
   gdy wybór jest istotnie niejednoznaczny, zadaj jedno krótkie pytanie.
3. select_track od razu uruchamia odtwarzanie. Po success=true zadanie
   włączenia tego utworu jest zakończone: zakończ turę bez wypowiedzi.
   Nie wywołuj potem play_pause, bo zatrzymasz właśnie włączoną muzykę.
4. play_pause przełącza stan: odtwarza wstrzymany utwór albo pauzuje grający.
   Używaj go do wznowienia/pauzy, a nie do wyboru utworu według życzenia.
   Polecenia „następny” i „poprzedni” wykonuj bez pobierania listy.
"""


def _format_address(street: str, city: str, number: str) -> str:
    street = re.sub(r'^(?:ulica\b|ul(?:\.|\b))\s*', '', street.strip(), flags=re.IGNORECASE)
    number = number.strip()
    street = re.sub(rf'\s+{re.escape(number)}$', '', street, flags=re.IGNORECASE)
    return f'ul. {street} {number}, {city.strip()}'


class Assistant:
    def __init__(self, car, thread_id: str = "user_session_1"):
        self.car = car
        self.checkpointer = InMemorySaver()
        self.thread_config: RunnableConfig = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": 8,
        }
        self.graph = build_graph(car)
        self.agent = self.initialize_agent()

    def _execute_graph_action(self, intent: str, action: str, payload: dict):
        state = self.graph.invoke({
            "intent": intent,
            "action": action,
            "payload": payload,
        })
        return state["result"]
        
    def build_tools(self):
        car = self.car
        self._listed_track_titles = set()

        # Muzyka
        @tool
        def play_pause():
            """Przełącza pauzę/odtwarzanie obecnego utworu; po select_track zatrzyma muzykę."""
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
            result = {
                "success": True,
                "tracks": [
                    {
                        "id": index,
                        "title": track["title"],
                        "author": track["artist"],
                    }
                    for index, track in enumerate(car.music.tracks)
                ],
                "message": "Retrieved track list successfully.",
            }
            self._listed_track_titles = {track["title"] for track in result["tracks"]}
            return result

        @tool
        def search_track(query: str):
            """Wyszukuje utwory po tytule lub wykonawcy."""
            matches = [
                {
                    "id": index,
                    "title": track["title"],
                    "author": track["artist"],
                }
                for index, track in enumerate(car.music.tracks)
                if query.lower() in track["title"].lower()
                or query.lower() in track["artist"].lower()
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
        def select_track(title: str, runtime: ToolRuntime = None):
            """Wybiera i od razu odtwarza utwór. Użyj dokładnego tytułu z get_track_list w tej turze. Po sukcesie nie wywołuj play_pause."""
            # Parallel calls in one response cannot use a library the model has not seen.
            if runtime is not None and any(
                call['name'] == 'get_track_list'
                for call in runtime.state['messages'][-1].tool_calls
            ):
                return {
                    "success": False,
                    "action": "select_track",
                    "message": "Poczekaj na wynik get_track_list, a dopiero potem wybierz utwór.",
                }
            if title not in self._listed_track_titles:
                return {
                    "success": False,
                    "action": "select_track",
                    "message": "Najpierw pobierz get_track_list i wybierz dokładny tytuł z tej listy.",
                }
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
            address = _format_address(street, city, number)
            return self._execute_graph_action(
                "navigation",
                "set_destination",
                {"address": address},
            )
            
        @tool
        def add_stop(street: str, city: str, number: str):
            """Dodaje przystanek do trasy na podany adres. street, city i number muszą być podane."""
            address = _format_address(street, city, number)
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
            model=ChatOllama(
                model=config.OLLAMA_MODEL,
                base_url="http://127.0.0.1:11434",
                temperature=0,
                client_kwargs={"trust_env": False},
            ),
            system_prompt=SYSTEM_PROMPT_SHORT,
            tools=self.build_tools(),
            checkpointer=self.checkpointer,
        )
    
    
    def handle_text(self, text: str, *, report=None, turn_id=None):
        self._listed_track_titles = set()
        config = self.thread_config
        if report is not None:
            config = merge_configs(config, {"callbacks": [SessionCallbacks(report, turn_id)]})
            report.emit("agent_start", turn_id=turn_id)
        input_data: InputAgentState = {"messages": [{"role": "user", "content": text}]}
        final_text = ""
        try:
            for raw_chunk in self.agent.stream(
                input_data, config=config, stream_mode="updates", version="v2",
            ):
                if not isinstance(raw_chunk, dict):
                    continue
                data = raw_chunk.get("data")
                if not isinstance(data, dict):
                    continue
                for raw_update in data.values():
                    if not isinstance(raw_update, dict):
                        continue
                    messages = raw_update.get("messages", [])
                    if not isinstance(messages, list):
                        continue
                    for message in messages:
                        if isinstance(message, AIMessage) and not message.tool_calls:
                            final_text = message.text
        except Exception as error:
            message = str(error)
            if isinstance(error, ConnectError):
                message = (
                    "Nie można połączyć się z Ollamą pod http://127.0.0.1:11434. "
                    "Uruchom aplikację Ollama lub polecenie 'ollama serve', "
                    "a następnie ponownie uruchom asystenta."
                )
            if report is not None:
                report.emit("agent_end", turn_id=turn_id, success=False, error=message)
            if isinstance(error, ConnectError):
                raise ConnectionError(message) from error
            raise
        if report is not None:
            report.emit("agent_end", turn_id=turn_id, success=True, text=final_text)
        return final_text
