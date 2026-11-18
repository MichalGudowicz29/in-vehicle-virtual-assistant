"""Task scenarios and the success criterion applied to one session report (stdlib only)."""

import json

EXPECTED_ARGUMENTS = {'name': 'Robert Lewandowski', 'number_type': 'mobile'}
SCENARIOS = {
    1: dict(title='Muzyka', tools=('select_track',),
            prompts=('Włącz piosenkę Christmas Eve',
                     'Włącz Christmas Eve, święta już blisko',
                     'Włącz jakąś muzykę, chcę poczuć klimat świąt'),
            state={'music': {'title': 'Christmas Eve', 'is_playing': True}},
            effect='Pobrano bibliotekę, następnie wybrano Christmas Eve dokładnie raz; utwór jest odtwarzany.'),
    2: dict(title='Telefon', tools=('call_contact',),
            prompts=('Zadzwoń do Roberta Lewandowskiego',
                     'Połącz mnie z Robertem Lewandowskim, musze mu coś powiedzieć',
                     'Zadzwoń do pierwszego mężczyzny jakiego mam w kontaktach'),
            state={'contacts': {'name': 'Robert Lewandowski', 'is_calling': True}},
            effect='call_contact(name="Robert Lewandowski", number_type="mobile") dokładnie raz; połączenie aktywne.'),
    3: dict(title='Nawigacja', tools=('navigate_to',),
            prompts=('Ustaw cel nawigacji na ulicę Żołnierska 47 w Szczecinie',
                     'Jedziemy na ulicę Żołnierską 47',
                     'Potrzebuje dojechać na Żołnierską, tam gdzie zawsze.'),
            state={'navigation': {'destination': 'ul. Żołnierska 47, Szczecin', 'stops': []}},
            effect='navigate_to dokładnie raz; cel ul. Żołnierska 47, Szczecin, bez przystanków.'),
}


def evaluate_session(data, task=2) -> tuple[bool, str]:
    scenario = SCENARIOS[task]
    if not isinstance(data, dict):
        return False, 'Niepoprawny format raportu.'
    events, turns = data.get('events'), data.get('turns')
    if (not isinstance(events, list) or not isinstance(turns, list)
            or not all(isinstance(item, dict) for item in events + turns)):
        return False, 'Brak poprawnej historii zdarzeń lub tur.'
    for event in events:
        if event.get('type') == 'session_error':
            return False, f"Błąd sesji: {event.get('error', 'brak szczegółów')}"
    if (len(turns) != 1 or turns[0].get('status') != 'completed'
            or not isinstance(turns[0].get('id'), int)):
        return False, 'Oczekiwano jednej poprawnie zakończonej tury.'
    calls = [e for e in events if e.get('type') == 'tool_start' and e.get('name') in scenario['tools']]
    if len(calls) != 1:
        return False, f"Oczekiwane narzędzia: {scenario['tools']}; liczba wywołań: {len(calls)}."
    for call in calls:
        if task == 2:
            arguments = call.get('arguments')
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    return False, 'Niepoprawny JSON argumentów call_contact.'
            if arguments != EXPECTED_ARGUMENTS:
                return False, f'Nieprawidłowe argumenty call_contact: {arguments!r}.'
        if not call.get('run_id') or call.get('turn_id') != turns[0].get('id'):
            return False, 'Wywołanie narzędzia nie jest przypisane do oczekiwanej tury.'
        ends = [e for e in events if e.get('type') == 'tool_end'
                and e.get('name') == call['name'] and e.get('run_id') == call['run_id']
                and e.get('turn_id') == call['turn_id']]
        if len(ends) != 1 or ends[0].get('success') is not True:
            return False, f"Brak potwierdzonego sukcesu właściwego {call['name']}."
    if task == 1:
        call = calls[0]
        arguments = call.get('arguments')
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                return False, 'Niepoprawny JSON argumentów select_track.'
        if arguments != {'title': 'Christmas Eve'}:
            return False, 'Wybrano niewłaściwy utwór.'
        if any(e.get('type') == 'tool_start' and e.get('name') in
               ('play_pause', 'pause_music', 'resume_music', 'next_track', 'previous_track') for e in events):
            return False, 'Wykonano dodatkową operację muzyczną.'
        preceding = events[:events.index(call)]
        responses = [e for e in preceding if e.get('type') == 'llm_end'
                     and e.get('turn_id') == call['turn_id']]
        if responses and 'get_track_list' in (responses[-1].get('tools') or []):
            return False, 'Pobranie biblioteki i wybór pochodzą z tej samej odpowiedzi modelu.'
        listed = False
        for index, event in enumerate(preceding):
            if (event.get('type') != 'tool_end' or event.get('name') != 'get_track_list'
                    or event.get('success') is not True or event.get('turn_id') != call['turn_id']
                    or not event.get('run_id')):
                continue
            if not any(e.get('type') == 'tool_start' and e.get('name') == 'get_track_list'
                       and e.get('run_id') == event['run_id'] and e.get('turn_id') == call['turn_id']
                       for e in preceding[:index]):
                continue
            output = event.get('output')
            if isinstance(output, str):
                try:
                    output = json.loads(output)
                except json.JSONDecodeError:
                    continue
            if isinstance(output, dict) and isinstance(output.get('tracks'), list):
                listed = any(isinstance(track, dict) and track.get('title') == arguments['title']
                             for track in output['tracks'])
        if not listed:
            return False, 'Brak potwierdzonego pobrania biblioteki z wybranym utworem przed select_track.'
    states = [e.get('state') for e in events if e.get('type') == 'app_state']
    if not states or not isinstance(states[-1], dict):
        return False, 'Brak zapisanego końcowego stanu aplikacji.'
    if any(states[-1].get(domain) != expected for domain, expected in scenario['state'].items()):
        return False, f"Końcowy stan nie spełnia oczekiwania: {scenario['state']!r}."
    return True, scenario['effect']
