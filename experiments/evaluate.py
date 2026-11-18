"""Task scenarios and the success criterion applied to one session report (stdlib only).

The criterion checks what the application executed: exactly one successful effect call of
the task's tool, the resolved target (contact + number type / track title) and the final
HMI state. Failed attempts before the successful call are allowed; duplicates of a
successful effect are blocked by the PlanGuard and would show up as a second success.
"""

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
    succeeded = []
    for call in calls:
        if not call.get('run_id') or call.get('turn_id') != turns[0].get('id'):
            return False, 'Wywołanie narzędzia nie jest przypisane do oczekiwanej tury.'
        ends = [e for e in events if e.get('type') == 'tool_end'
                and e.get('name') == call['name'] and e.get('run_id') == call['run_id']
                and e.get('turn_id') == call['turn_id']]
        if len(ends) != 1:
            return False, f"Wywołanie {call['name']} bez jednoznacznego zakończenia."
        if ends[0].get('success') is True:
            succeeded.append((call, ends[0]))
    if len(succeeded) != 1:
        return False, (f"Oczekiwano dokładnie jednego udanego {scenario['tools']}; "
                       f"udanych: {len(succeeded)}, wszystkich wywołań: {len(calls)}.")
    target = _resolved_target(*succeeded[0])
    if task == 2 and (target.get('contact_name', target.get('name')), target.get('number_type')) != (
            EXPECTED_ARGUMENTS['name'], EXPECTED_ARGUMENTS['number_type']):
        return False, f'Połączono z niewłaściwym kontaktem lub numerem: {target!r}.'
    if task == 1:
        if target.get('title') != 'Christmas Eve':
            return False, 'Wybrano niewłaściwy utwór.'
        if any(e.get('type') == 'tool_start' and e.get('name') in
               ('play_pause', 'pause_music', 'resume_music', 'next_track', 'previous_track') for e in events):
            return False, 'Wykonano dodatkową operację muzyczną.'
    states = [e.get('state') for e in events if e.get('type') == 'app_state']
    if not states or not isinstance(states[-1], dict):
        return False, 'Brak zapisanego końcowego stanu aplikacji.'
    if any(states[-1].get(domain) != expected for domain, expected in scenario['state'].items()):
        return False, f"Końcowy stan nie spełnia oczekiwania: {scenario['state']!r}."
    return True, scenario['effect']


def _json(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return {}
    return value if isinstance(value, dict) else {}


def _resolved_target(call, end):
    """What the application actually executed: resolved values from the tool result
    (version 2 tools resolve spoken names), falling back to the model's arguments."""
    return {**_json(call.get('arguments')), **_json(end.get('output'))}
