from typing import Any

from ..state import HMIState


def navigation_node(state: HMIState, car: Any) -> dict[str, dict[str, Any]]:
    payload = state["payload"] if "payload" in state else {}
    car.navigation.set_destination(payload["address"])

    return {
        "result": {
            "success": True,
            "action": "set_destination",
        }
    }
