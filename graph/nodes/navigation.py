from typing import Any

from ..state import HMIState


def navigation_node(state: HMIState, car: Any) -> dict[str, dict[str, Any]]:
    payload = state["payload"] if "payload" in state else {}
    address = payload["address"]
    success = bool(address.strip())

    if success:
        car.navigation.set_destination(address)

    return {
        "result": {
            "success": success,
            "action": "set_destination",
            "destination": address,
        }
    }
