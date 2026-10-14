from typing import Any

from .state import HMIState


def route_node(state: HMIState, car: Any) -> dict[str, str]:
    intent = state["intent"] if "intent" in state else "unknown"
    route = intent if intent in {"contacts", "music", "navigation"} else "unknown"
    return {"route": route}
