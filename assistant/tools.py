"""LLM tools: read-only lookups and guarded effects on the car controllers.

Tool names, docstrings, arguments and result dictionaries are part of the model input.
Change against the 16.11 series (2026-11-18): navigate_to/add_stop take the address as
spoken and the application matches it to the place base, instead of street/city/number
fields that made a small model invent a missing city.
"""

from typing import Annotated, Literal

from langchain.tools import InjectedToolArg, ToolRuntime, tool  # type: ignore

from .plan_guard import ActionName, PlanGuard


def perform(car, action: str, payload: dict) -> dict:
    """Call one controller operation and describe its outcome for the model."""
    music = car.music
    if action == 'call_contact':
        requested = car.contacts.call_contact(payload['name'], payload['number_type'])
        return {'success': bool(requested), 'action': action,
                'contact_name': payload['name'], 'number_type': payload['number_type']}
    if action in ('set_destination', 'add_stop'):
        navigation = car.navigation
        address = payload['address']
        method = navigation.set_destination if action == 'set_destination' else navigation.add_stop
        if address.strip() and method(address):
            matched = navigation.destination if action == 'set_destination' else navigation.stops[-1]['address']
            return {'success': True, 'action': action,
                    'destination' if action == 'set_destination' else 'stop': matched}
        candidates = [place['address'] for place in navigation.search_places(address)]
        return {'success': False, 'action': action,
                'message': ('Adres niejednoznaczny: wybierz jeden z kandydatów albo dopytaj użytkownika.'
                            if candidates else
                            'Nie ma takiego adresu w bazie miejsc. Nie zgaduj; dopytaj użytkownika.'),
                'candidates': candidates or [place['address'] for place in navigation.places_list.values()]}
    if action == 'set_playback':
        requested = music.set_playback(payload['playing'])
    elif action == 'next_track':
        requested = music.next_track()
    elif action == 'previous_track':
        requested = music.previous_track()
    elif action == 'select_track':
        requested = music.select_track(payload['title'])
    else:
        raise ValueError(f'Unknown action: {action}')
    return {'success': bool(requested), 'action': action,
            'isPlaying': music.isPlaying, 'currentTrackIndex': music.currentTrackIndex}


def build_tools(car, guard: PlanGuard) -> list:
    def guarded(name, action, payload):
        # `perform` is looked up at call time so tests can observe controller calls.
        return guard.execute(name, action, payload, lambda: perform(car, action, payload))

    @tool
    def set_action_plan(actions: list[ActionName], answer_required: bool = False):
        """Zapisuje kolejność wszystkich żądanych akcji wykonawczych w tej turze. Bez narzędzi pobierających dane. Plan jest niezmienny; zapisz go przed wykonaniem akcji."""
        return guard.set_plan(actions, answer_required)

    # Muzyka
    @tool
    def pause_music():
        """Pauzuje muzykę. Już zatrzymana muzyka pozostaje zatrzymana."""
        return guarded('pause_music', 'set_playback', {'playing': False})

    @tool
    def resume_music():
        """Wznawia muzykę. Już odtwarzana muzyka pozostaje włączona."""
        return guarded('resume_music', 'set_playback', {'playing': True})

    @tool
    def next_track():
        """Przełącza na następny utwór."""
        return guarded('next_track', 'next_track', {})

    @tool
    def previous_track():
        """Przełącza na poprzedni utwór."""
        return guarded('previous_track', 'previous_track', {})

    @tool
    def get_track_list():
        """Zwraca listę dostępnych utworów."""
        tracks = [{"id": index, "title": track["title"], "author": track["artist"]}
                  for index, track in enumerate(car.music.tracks)]
        guard.listed_track_titles = {track["title"] for track in tracks}
        return {"success": True, "tracks": tracks, "message": "Retrieved track list successfully."}

    @tool
    def search_track(query: str):
        """Wyszukuje utwory po tytule lub wykonawcy."""
        # Known limitation kept for comparability: matches found here do not unlock select_track.
        matches = [{"id": index, "title": track["title"], "author": track["artist"]}
                   for index, track in enumerate(car.music.tracks)
                   if query.lower() in track["title"].lower() or query.lower() in track["artist"].lower()]
        return {"success": bool(matches), "tracks": matches,
                "message": f"Found {len(matches)} matching tracks." if matches else "No tracks found."}

    @tool
    def select_track(title: str, runtime: Annotated[ToolRuntime | None, InjectedToolArg] = None):
        """Wybiera i od razu odtwarza utwór. Użyj dokładnego tytułu z get_track_list w tej turze. Nie pauzuj bez żądania użytkownika."""
        # Parallel calls in one response cannot use a library the model has not seen.
        if runtime is not None and any(call['name'] == 'get_track_list'
                                       for call in runtime.state['messages'][-1].tool_calls):
            return {"success": False, "action": "select_track",
                    "message": "Poczekaj na wynik get_track_list, a dopiero potem wybierz utwór."}
        if title not in guard.listed_track_titles:
            return {"success": False, "action": "select_track",
                    "message": "Najpierw pobierz get_track_list i wybierz dokładny tytuł z tej listy."}
        return guarded('select_track', 'select_track', {"title": title})

    # Kontakty
    @tool
    def get_contacts():
        """Zwraca wszystkich zapisanych kontaktów wraz ze wszystkimi numerami."""
        contacts = [{"id": index, "name": contact["name"],
                     "numbers": {key: value for key, value in contact.items() if key != "name"}}
                    for index, contact in enumerate(car.contacts.contacts)]
        return {"success": bool(contacts), "contacts": contacts, "message": "Lista kontaktów została pobrana."}

    @tool
    def call_contact(name: str, number_type: Literal["mobile", "work"]):
        """Inicjuje połączenie z kontaktem o podanej nazwie i typie numeru."""
        return guarded('call_contact', 'call_contact', {"name": name, "number_type": number_type})

    # Nawigacja
    @tool
    def navigate_to(address: str):
        """Ustawia cel nawigacji. address: adres dokładnie tak, jak podał użytkownik, np. "Żołnierska 47"; nie dopisuj miasta ani numeru, których nie podał. Aplikacja dopasuje adres do bazy miejsc; gdy się nie uda, zwróci kandydatów."""
        return guarded('navigate_to', 'set_destination', {"address": address.strip()})

    @tool
    def add_stop(address: str):
        """Dodaje przystanek do trasy. address: adres tak, jak podał użytkownik; aplikacja dopasuje go do bazy miejsc i przy niepowodzeniu zwróci kandydatów."""
        return guarded('add_stop', 'add_stop', {"address": address.strip()})

    @tool
    def get_places_list():
        """Zwraca listę dostępnych miejsc, ktore mozna dodac jako przystanek."""
        return {"success": True, "places": car.navigation.places_list,
                "message": "Retrieved places list successfully."}

    # Order matters: it is the order of tool schemas in the model request.
    return [set_action_plan, pause_music, resume_music, next_track, previous_track, search_track,
            select_track, get_track_list, call_contact, get_contacts, navigate_to, add_stop,
            get_places_list]


LOOKUP_TOOLS = ('get_contacts', 'get_track_list', 'search_track', 'get_places_list')
