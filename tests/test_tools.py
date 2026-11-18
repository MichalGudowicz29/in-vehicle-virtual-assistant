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


def test_music_selection_requires_current_library_and_starts_playback():
    car = CarSystem()
    assistant = Assistant.__new__(Assistant)
    assistant.car = car
    tools = {tool.name: tool for tool in assistant.build_tools()}
    tools['set_action_plan'].invoke({'actions': ['select_track']})
    assert tools['select_track'].invoke({'title': 'Chill song'})['success'] is False
    assert set(tools['select_track'].tool_call_schema.model_json_schema()['properties']) == {'title'}
    assert car.music.currentTrackIndex == 0
    assert car.music.isPlaying is False
    tools['search_track'].invoke({'query': 'Chill'})
    assert tools['select_track'].invoke({'title': 'Chill song'})['success'] is False
    tools['get_track_list'].invoke({})
    assert tools['select_track'].invoke({'title': 'chill song'})['success'] is False
    assert tools['select_track'].invoke({'title': 'Chill song'})['success'] is True
    assert car.music.currentTrackIndex == 1
    assert car.music.isPlaying is True

def test_selection_rechecks_library_after_listing():
    car = CarSystem()
    assistant = Assistant.__new__(Assistant)
    assistant.car = car
    tools = {tool.name: tool for tool in assistant.build_tools()}
    tools['set_action_plan'].invoke({'actions': ['select_track']})
    tools['get_track_list'].invoke({})
    car.music.tracks.pop()
    assert tools['select_track'].invoke({'title': 'Dynamic music'})['success'] is False


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
