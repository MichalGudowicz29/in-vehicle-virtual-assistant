"""LLM tools: read-only lookups and guarded effects on the car controllers.

Division of work: the LLM understands the command and passes on *what the user said*
("Roberta", "Żołnierska 47", "Christmas Eve"); the application resolves it against its
own data (contacts, places, tracks). One match is executed; several matches or none are
returned as candidates so the LLM can ask a short question instead of guessing.
"""

from langchain.tools import tool  # type: ignore

from CarSystem.matching import all_terms_match, tokens

from .plan_guard import ActionName, PlanGuard

NUMBER_LABELS = {'mobile': 'mobilny', 'work': 'służbowy'}
# The model may answer with the Polish label it saw in a result or heard from the user.
NUMBER_ALIASES = {'mobile': 'mobile', 'mobilny': 'mobile', 'komorkowy': 'mobile', 'komórkowy': 'mobile',
                  'prywatny': 'mobile', 'work': 'work', 'sluzbowy': 'work', 'służbowy': 'work', 'praca': 'work'}


def find_tracks(tracks: list[dict], query: str) -> list[dict]:
    """Tracks whose title or artist matches what the user said."""
    terms = tokens(query)
    exact = [t for t in tracks if tokens(t['title']) == terms or tokens(t['artist']) == terms]
    return exact or [t for t in tracks if all_terms_match(terms, tokens(f"{t['title']} {t['artist']}"))]


def _call(car, payload: dict) -> dict:
    contacts = car.contacts
    matches = contacts.find_contacts(payload['name'])
    if len(matches) != 1:
        return {'success': False, 'action': 'call_contact',
                'message': ('Kilka pasujących kontaktów: zapytaj użytkownika, którego wybrać.' if matches
                            else 'Brak takiego kontaktu. Powiedz o tym krótko; nie wybieraj innego.'),
                'candidates': [c['name'] for c in (matches or contacts.contacts)]}
    contact = matches[0]
    numbers = [key for key in contact if key != 'name']
    requested_type = NUMBER_ALIASES.get((payload.get('number_type') or '').strip().lower(), payload.get('number_type'))
    number_type = requested_type or (numbers[0] if len(numbers) == 1 else None)
    if number_type not in numbers:
        return {'success': False, 'action': 'call_contact', 'contact_name': contact['name'],
                'message': ('Kontakt ma kilka numerów: zapytaj, który wybrać.' if number_type is None
                            else 'Kontakt nie ma numeru tego typu: zapytaj, który wybrać.'),
                'number_types': [NUMBER_LABELS.get(n, n) for n in numbers]}
    requested = contacts.call_contact(contact['name'], number_type)
    return {'success': bool(requested), 'action': 'call_contact',
            'contact_name': contact['name'], 'number_type': number_type}


def _route(car, action: str, payload: dict) -> dict:
    navigation = car.navigation
    address = payload['address']
    method = navigation.set_destination if action == 'set_destination' else navigation.add_stop
    if address.strip() and method(address):
        matched = navigation.destination if action == 'set_destination' else navigation.stops[-1]['address']
        return {'success': True, 'action': action,
                'destination' if action == 'set_destination' else 'stop': matched}
    candidates = [place['address'] for place in navigation.search_places(address)]
    return {'success': False, 'action': action,
            'message': ('Kilka pasujących adresów: zapytaj użytkownika, który wybrać.' if candidates
                        else 'Brak takiego adresu w zapisanych miejscach. Powiedz o tym krótko; nie zgaduj.'),
            'candidates': candidates or [place['address'] for place in navigation.places_list.values()]}


def perform(car, action: str, payload: dict) -> dict:
    """Resolve the spoken target, call one controller operation and describe the outcome."""
    music = car.music
    if action == 'call_contact':
        return _call(car, payload)
    if action in ('set_destination', 'add_stop'):
        return _route(car, action, payload)
    if action == 'remove_stop':
        navigation = car.navigation
        if navigation.remove_stop(payload['address']):
            return {'success': True, 'action': action, 'stops': [s['address'] for s in navigation.stops]}
        return {'success': False, 'action': action,
                'message': 'Nie ma takiego przystanku na trasie. Powiedz o tym krótko.',
                'stops': [s['address'] for s in navigation.stops]}
    if action == 'clear_route':
        return {'success': bool(car.navigation.clear_route()), 'action': action}
    if action == 'select_track':
        matches = find_tracks(music.tracks, payload['title'])
        if len(matches) != 1:
            return {'success': False, 'action': action,
                    'message': ('Kilka pasujących utworów: zapytaj, który włączyć.' if matches
                                else 'Brak takiego utworu. Wybierz z biblioteki tylko pasujący albo powiedz o braku.'),
                    'candidates': [t['title'] for t in (matches or music.tracks)]}
        requested = music.select_track(matches[0]['title'])
        return {'success': bool(requested), 'action': action, 'title': matches[0]['title'],
                'isPlaying': music.isPlaying}
    if action == 'set_playback':
        requested = music.set_playback(payload['playing'])
    elif action == 'next_track':
        requested = music.next_track()
    elif action == 'previous_track':
        requested = music.previous_track()
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
        """Zwraca bibliotekę utworów. Potrzebne tylko, gdy użytkownik opisuje nastrój lub gatunek zamiast tytułu."""
        tracks = [{"title": track["title"], "author": track["artist"]} for track in car.music.tracks]
        return {"success": True, "tracks": tracks}

    @tool
    def select_track(title: str):
        """Wybiera i od razu odtwarza utwór. title: tytuł lub wykonawca tak, jak podał użytkownik (albo tytuł z get_track_list); aplikacja dopasuje utwór. Nie pauzuj bez żądania użytkownika."""
        return guarded('select_track', 'select_track', {"title": title.strip()})

    # Kontakty
    @tool
    def get_contacts():
        """Zwraca kontakty z numerami. Potrzebne tylko do pytań o kontakty, nie do dzwonienia."""
        contacts = [{"name": contact["name"],
                     "numbers": [NUMBER_LABELS.get(k, k) for k in contact if k != "name"]}
                    for contact in car.contacts.contacts]
        return {"success": True, "contacts": contacts}

    @tool
    def call_contact(name: str, number_type: str | None = None):
        """Dzwoni do kontaktu. name: imię i/lub nazwisko tak, jak powiedział użytkownik (np. "Roberta"); aplikacja dopasuje kontakt. number_type ("mobilny" albo "służbowy") tylko, gdy użytkownik sam wskazał typ; jeśli nie wskazał, a kontakt ma kilka numerów, zapytaj go."""
        return guarded('call_contact', 'call_contact', {"name": name.strip(), "number_type": number_type})

    # Nawigacja
    @tool
    def navigate_to(address: str):
        """Ustawia cel nawigacji. address: adres tak, jak podał użytkownik (np. "Żołnierska 47"); nie dopisuj miasta ani numeru. Aplikacja dopasuje adres do zapisanych miejsc."""
        return guarded('navigate_to', 'set_destination', {"address": address.strip()})

    @tool
    def add_stop(address: str):
        """Dodaje przystanek do trasy. address: adres tak, jak podał użytkownik; aplikacja dopasuje go do zapisanych miejsc."""
        return guarded('add_stop', 'add_stop', {"address": address.strip()})

    @tool
    def remove_stop(address: str):
        """Usuwa przystanek z trasy. address: adres przystanku tak, jak podał użytkownik."""
        return guarded('remove_stop', 'remove_stop', {"address": address.strip()})

    @tool
    def clear_route():
        """Czyści trasę: usuwa cel i wszystkie przystanki."""
        return guarded('clear_route', 'clear_route', {})

    @tool
    def get_places_list():
        """Zwraca zapisane miejsca. Potrzebne tylko do pytań o miejsca, nie do ustawiania celu."""
        return {"success": True, "places": [p["address"] for p in car.navigation.places_list.values()]}

    # Order matters: it is the order of tool schemas in the model request.
    return [set_action_plan, pause_music, resume_music, next_track, previous_track,
            select_track, get_track_list, call_contact, get_contacts, navigate_to, add_stop,
            remove_stop, clear_route, get_places_list]


LOOKUP_TOOLS = ('get_contacts', 'get_track_list', 'get_places_list')
