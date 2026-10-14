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
    }
    assert car.music.isPlaying is True
