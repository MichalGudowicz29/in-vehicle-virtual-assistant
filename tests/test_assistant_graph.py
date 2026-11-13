import pytest

from assistant import Assistant
from CarSystem.car_system import CarSystem
from graph import build_graph


def test_assistant_delegates_music_action_to_graph():
    car = CarSystem()
    assistant = Assistant.__new__(Assistant)
    assistant.graph = build_graph(car)

    result = assistant._execute_graph_action(
        "music",
        "play_pause",
        {},
    )

    assert result == {
        "success": True,
        "action": "play_pause",
        "isPlaying": True,
        "currentTrackIndex": 0,
    }
    assert car.music.isPlaying is True


def test_select_track_tool_returns_graph_failure():
    car = CarSystem()
    assistant = Assistant.__new__(Assistant)
    assistant.car = car
    assistant.graph = build_graph(car)

    tools = {tool.name: tool for tool in assistant.build_tools()}
    select_track = tools['select_track']
    tools['get_track_list'].invoke({})

    result = select_track.invoke({"title": "Unknown track"})

    assert result["success"] is False


def test_music_selection_requires_current_library_and_starts_playback():
    from types import SimpleNamespace

    car = CarSystem()
    assistant = Assistant.__new__(Assistant)
    assistant.car = car
    assistant.graph = build_graph(car)
    tools = {tool.name: tool for tool in assistant.build_tools()}
    assert tools['select_track'].invoke({'title': 'Chill song'})['success'] is False
    assert car.music.currentTrackIndex == 0
    assert car.music.isPlaying is False
    tools['search_track'].invoke({'query': 'Chill'})
    assert tools['select_track'].invoke({'title': 'Chill song'})['success'] is False
    tools['get_track_list'].invoke({})
    assert tools['select_track'].invoke({'title': 'chill song'})['success'] is False
    assert tools['select_track'].invoke({'title': 'Chill song'})['success'] is True
    assert car.music.currentTrackIndex == 1
    assert car.music.isPlaying is True

    # A new user turn must not reuse authorization from the previous list.
    assistant.thread_config = {}
    assistant.agent = SimpleNamespace(stream=lambda *args, **kwargs: iter(()))
    assistant.handle_text('Włącz Christmas Eve')
    assert tools['select_track'].invoke({'title': 'Christmas Eve'})['success'] is False
    assert car.music.currentTrackIndex == 1


def test_selection_rechecks_library_after_listing():
    car = CarSystem()
    assistant = Assistant.__new__(Assistant)
    assistant.car = car
    assistant.graph = build_graph(car)
    tools = {tool.name: tool for tool in assistant.build_tools()}
    tools['get_track_list'].invoke({})
    car.music.tracks.pop()
    assert tools['select_track'].invoke({'title': 'Dynamic music'})['success'] is False


@pytest.mark.parametrize('tool_name', ['navigate_to', 'add_stop'])
@pytest.mark.parametrize('street, number', [
    ('Żołnierska', '47'),
    ('ul. Żołnierska', '47'),
    ('UL.Żołnierska', '47'),
    ('ulica Żołnierska', '47'),
    ('  ul. Żołnierska 47  ', ' 47 '),
    ('Żołnierska 47', '47'),
])
def test_address_tools_accept_street_with_or_without_prefix_and_house_number(tool_name, street, number):
    car = CarSystem()
    assistant = Assistant.__new__(Assistant)
    assistant.car = car
    assistant.graph = build_graph(car)
    tool = next(tool for tool in assistant.build_tools() if tool.name == tool_name)
    result = tool.invoke({'street': street, 'city': 'Szczecin', 'number': number})
    assert result['success'] is True
    assert result['destination' if tool_name == 'navigate_to' else 'stop'] == 'ul. Żołnierska 47, Szczecin'
    assert car.navigation.routePoints[-1]['address'] == 'ul. Żołnierska 47, Szczecin'


@pytest.mark.parametrize('street', ['ul. Żołnierska 147', 'ul. Żołnierska 47a'])
def test_address_tool_does_not_silently_replace_conflicting_house_number(street):
    car = CarSystem()
    assistant = Assistant.__new__(Assistant)
    assistant.car = car
    assistant.graph = build_graph(car)
    tool = next(tool for tool in assistant.build_tools() if tool.name == 'navigate_to')
    assert tool.invoke({'street': street, 'city': 'Szczecin', 'number': '47'})['success'] is False
    assert car.navigation.destination == ''
