import pytest

from assistant import Assistant
from CarSystem.car_system import CarSystem
from assistant.tools import perform


def test_planned_resume_reaches_music_controller():
    car = CarSystem()
    assistant = Assistant.__new__(Assistant)
    assistant.car = car

    tools = {tool.name: tool for tool in assistant.build_tools()}
    tools['set_action_plan'].invoke({'actions': ['resume_music']})

    result = tools['resume_music'].invoke({})

    assert result == {
        "success": True,
        "action": "set_playback",
        "isPlaying": True,
        "currentTrackIndex": 0,
    }
    assert car.music.isPlaying is True


def test_select_track_tool_returns_failure_for_unknown_title():
    car = CarSystem()
    assistant = Assistant.__new__(Assistant)
    assistant.car = car

    tools = {tool.name: tool for tool in assistant.build_tools()}
    select_track = tools['select_track']
    tools['set_action_plan'].invoke({'actions': ['select_track']})
    tools['get_track_list'].invoke({})

    result = select_track.invoke({"title": "Unknown track"})

    assert result["success"] is False


@pytest.mark.parametrize('spoken', ['Chill song', 'chill', 'Fleetwood Mac'])
def test_music_selection_matches_spoken_title_or_artist_and_starts_playback(spoken):
    car = CarSystem()
    assistant = Assistant.__new__(Assistant)
    assistant.car = car
    tools = {tool.name: tool for tool in assistant.build_tools()}
    tools['set_action_plan'].invoke({'actions': ['select_track']})
    result = tools['select_track'].invoke({'title': spoken})
    assert result['success'] is True and result['title'] == 'Chill song'
    assert car.music.currentTrackIndex == 1 and car.music.isPlaying is True


@pytest.mark.parametrize('spoken, contact, number', [
    ('Roberta', 'Robert Lewandowski', 'mobile'),
    ('Roberta Lewandowskiego', 'Robert Lewandowski', 'mobile'),
    ('Jana Nowaka', 'Jan Nowak', 'work'),
])
def test_call_contact_resolves_spoken_name_and_single_number(spoken, contact, number):
    car = CarSystem()
    assistant = Assistant.__new__(Assistant)
    assistant.car = car
    tools = {tool.name: tool for tool in assistant.build_tools()}
    tools['set_action_plan'].invoke({'actions': ['call_contact']})
    result = tools['call_contact'].invoke({'name': spoken})
    assert result == {'success': True, 'action': 'call_contact', 'contact_name': contact, 'number_type': number}
    assert car.contacts.currentContactName == contact


def test_call_contact_asks_when_number_or_person_is_ambiguous():
    car = CarSystem()
    assistant = Assistant.__new__(Assistant)
    assistant.car = car
    tools = {tool.name: tool for tool in assistant.build_tools()}
    tools['set_action_plan'].invoke({'actions': ['call_contact']})
    anna = tools['call_contact'].invoke({'name': 'Anny'})
    assert anna['success'] is False and anna['number_types'] == ['mobilny', 'służbowy']
    assert car.contacts.isCalling is False
    car.contacts.set_contacts([{'name': 'Robert Kubica', 'mobile': '1'}])
    tools['set_action_plan'].invoke({'actions': ['call_contact']})
    roberts = tools['call_contact'].invoke({'name': 'Roberta'})
    assert roberts['candidates'] == ['Robert Lewandowski', 'Robert Kubica']
    assert car.contacts.isCalling is False


@pytest.mark.parametrize('tool_name', ['navigate_to', 'add_stop'])
@pytest.mark.parametrize('address', [
    'Żołnierska 47',
    'ul. Żołnierska 47, Szczecin',
    'ulica Żołnierską 47',
    'na Żołnierską 47 w Szczecinie',
    'Żołnierskiej 47',
])
def test_address_tools_match_spoken_address_to_place_base(tool_name, address):
    car = CarSystem()
    assistant = Assistant.__new__(Assistant)
    assistant.car = car
    tools = {tool.name: tool for tool in assistant.build_tools()}
    tools['set_action_plan'].invoke({'actions': [tool_name]})
    result = tools[tool_name].invoke({'address': address})
    assert result['success'] is True
    assert result['destination' if tool_name == 'navigate_to' else 'stop'] == 'ul. Żołnierska 47, Szczecin'
    assert car.navigation.routePoints[-1]['address'] == 'ul. Żołnierska 47, Szczecin'


@pytest.mark.parametrize('address', ['ul. Żołnierska 147', 'Żołnierska 47a', 'Żołnierska 47, Warszawa'])
def test_address_tool_rejects_other_address_and_offers_candidates(address):
    car = CarSystem()
    assistant = Assistant.__new__(Assistant)
    assistant.car = car
    tools = {tool.name: tool for tool in assistant.build_tools()}
    tools['set_action_plan'].invoke({'actions': ['navigate_to']})
    result = tools['navigate_to'].invoke({'address': address})
    assert result['success'] is False
    assert 'ul. Żołnierska 47, Szczecin' in result['candidates']
    assert car.navigation.destination == ''


def test_address_tool_schema_takes_only_spoken_address():
    assistant = Assistant.__new__(Assistant)
    assistant.car = CarSystem()
    tools = {tool.name: tool for tool in assistant.build_tools()}
    for name in ('navigate_to', 'add_stop'):
        assert set(tools[name].tool_call_schema.model_json_schema()['properties']) == {'address'}


def test_perform_reports_controller_outcome_for_the_model():
    car = CarSystem()
    assert perform(car, 'call_contact', {'name': 'Robert Lewandowski', 'number_type': 'mobile'}) == {
        'success': True, 'action': 'call_contact', 'contact_name': 'Robert Lewandowski', 'number_type': 'mobile'}
    failed = perform(car, 'set_destination', {'address': '  '})
    assert failed['success'] is False and len(failed['candidates']) == 3
    with pytest.raises(ValueError):
        perform(car, 'play_pause', {})


@pytest.mark.parametrize('number_type', ['mobilny', 'mobile', 'Komórkowy'])
def test_call_contact_accepts_polish_number_labels(number_type):
    car = CarSystem()
    assistant = Assistant.__new__(Assistant)
    assistant.car = car
    tools = {tool.name: tool for tool in assistant.build_tools()}
    tools['set_action_plan'].invoke({'actions': ['call_contact']})
    result = tools['call_contact'].invoke({'name': 'Anny Kowalskiej', 'number_type': number_type})
    assert result['success'] is True and result['number_type'] == 'mobile'


def test_voice_can_remove_stop_and_clear_route():
    car = CarSystem()
    assistant = Assistant.__new__(Assistant)
    assistant.car = car
    tools = {tool.name: tool for tool in assistant.build_tools()}
    tools['set_action_plan'].invoke({'actions': ['navigate_to', 'add_stop', 'remove_stop', 'clear_route']})
    assert tools['navigate_to'].invoke({'address': 'Żołnierska'})['success']
    assert tools['add_stop'].invoke({'address': 'stacyjna'})['success']
    assert tools['remove_stop'].invoke({'address': 'na Stacyjnej'}) == {
        'success': True, 'action': 'remove_stop', 'stops': []}
    assert tools['clear_route'].invoke({})['success']
    assert car.navigation.destination == '' and car.navigation.stops == []
