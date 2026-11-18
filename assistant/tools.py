"""LLM tools: read-only lookups and guarded effects on the car controllers.

Tool names, docstrings, arguments and result dictionaries are part of the model input;
they are unchanged from the version measured in the 16.11 series.
"""

import re
from typing import Annotated, Literal

from langchain.tools import InjectedToolArg, ToolRuntime, tool  # type: ignore

from .plan_guard import ActionName, PlanGuard


def format_address(street: str, city: str, number: str) -> str:
    street = re.sub(r'^(?:ulica\b|ul(?:\.|\b))\s*', '', street.strip(), flags=re.IGNORECASE)
    number = number.strip()
    street = re.sub(rf'\s+{re.escape(number)}$', '', street, flags=re.IGNORECASE)
    return f'ul. {street} {number}, {city.strip()}'


def perform(car, action: str, payload: dict) -> dict:
    """Call one controller operation and describe its outcome for the model."""
    music = car.music
    if action == 'call_contact':
        requested = car.contacts.call_contact(payload['name'], payload['number_type'])
        return {'success': bool(requested), 'action': action,
                'contact_name': payload['name'], 'number_type': payload['number_type']}
    if action in ('set_destination', 'add_stop'):
        address = payload['address']
        method = car.navigation.set_destination if action == 'set_destination' else car.navigation.add_stop
        success = bool(address.strip()) and bool(method(address))
        field = 'destination' if action == 'set_destination' else 'stop'
        return {'success': success, 'action': action, field: address}
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
    def navigate_to(street: str, city: str, number: str):
        """Ustawia cel nawigacji na podany adres. street, city i number muszą być podane."""
        return guarded('navigate_to', 'set_destination', {"address": format_address(street, city, number)})

    @tool
    def add_stop(street: str, city: str, number: str):
        """Dodaje przystanek do trasy na podany adres. street, city i number muszą być podane."""
        return guarded('add_stop', 'add_stop', {"address": format_address(street, city, number)})

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
