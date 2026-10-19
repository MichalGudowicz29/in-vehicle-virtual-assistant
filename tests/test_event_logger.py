import json

from evaluation.event_logger import EventLogger


def test_logger_writes_event_with_run_id_as_jsonl(tmp_path):
    logger = EventLogger(tmp_path, run_id="run-1")

    logger.record("turn_started", "turn-1", source="microphone")

    assert json.loads((tmp_path / "run-1.jsonl").read_text()) == {
        "type": "turn_started",
        "turn_id": "turn-1",
        "run_id": "run-1",
        "source": "microphone",
    }


def test_logger_keeps_appended_events_in_memory(tmp_path):
    logger = EventLogger(tmp_path, run_id="run-1")

    logger.append({"type": "graph_action_finished", "turn_id": "turn-1"})

    assert logger.events == [{
        "type": "graph_action_finished",
        "turn_id": "turn-1",
        "run_id": "run-1",
    }]
