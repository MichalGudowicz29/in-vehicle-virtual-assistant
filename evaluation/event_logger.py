import json
from pathlib import Path
from uuid import uuid4


class EventLogger:
    def __init__(self, output_dir: Path, run_id: str | None = None):
        self.run_id = run_id or str(uuid4())
        self.path = output_dir / f"{self.run_id}.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.events: list[dict] = []

    def append(self, event: dict) -> None:
        logged_event = {**event, "run_id": self.run_id}
        self.events.append(logged_event)
        with self.path.open("a", encoding="utf-8") as run_file:
            run_file.write(json.dumps(logged_event, ensure_ascii=False) + "\n")
            run_file.flush()

    def record(self, event_type: str, turn_id: str | None = None, **details) -> None:
        self.append({"type": event_type, "turn_id": turn_id, **details})
