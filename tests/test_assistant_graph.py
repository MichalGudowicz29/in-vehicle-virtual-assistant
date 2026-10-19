from assistant import Assistant
from CarSystem.car_system import CarSystem
from graph import build_graph
import pytest


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


def test_graph_action_records_started_and_finished_events():
    car = CarSystem()
    assistant = Assistant.__new__(Assistant)
    assistant.graph = build_graph(car)
    assistant.execution_events = []

    assistant._execute_graph_action("music", "play_pause", {})

    started, finished = assistant.execution_events
    assert started["type"] == "graph_action_started"
    assert started["intent"] == "music"
    assert started["action"] == "play_pause"
    assert started["payload"] == {}
    assert isinstance(started["time_ns"], int)
    assert finished["type"] == "graph_action_finished"
    assert finished["intent"] == "music"
    assert finished["action"] == "play_pause"
    assert finished["success"] is True
    assert finished["duration_ms"] >= 0
    assert finished["time_ns"] >= started["time_ns"]


def test_graph_action_records_failure_before_reraising_error():
    class FailingGraph:
        def invoke(self, state):
            raise RuntimeError("graph unavailable")

    assistant = Assistant.__new__(Assistant)
    assistant.graph = FailingGraph()
    assistant.execution_events = []

    with pytest.raises(RuntimeError, match="graph unavailable"):
        assistant._execute_graph_action("music", "play_pause", {})

    assert assistant.execution_events[1]["type"] == "graph_action_failed"
    assert assistant.execution_events[1]["error_type"] == "RuntimeError"
    assert assistant.execution_events[1]["error_message"] == "graph unavailable"
    assert assistant.execution_events[1]["duration_ms"] >= 0
