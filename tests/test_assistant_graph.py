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

    select_track = next(
        tool for tool in assistant.build_tools() if tool.name == "select_track"
    )

    result = select_track.invoke({"title": "Unknown track"})

    assert result["success"] is False
