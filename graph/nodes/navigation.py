from typing import Any

from ..state import HMIState


def navigation_node(state: HMIState, car: Any) -> dict[str, dict[str, Any]]:
    payload = state["payload"] if "payload" in state else {}
    address = payload["address"]
    action = state["action"] if "action" in state else None


    if action == "add_stop":
        success = bool(address.strip()) and bool(car.navigation.add_stop(address))
        return {
            "result": {
                "success": success,
                "action": "add_stop",
                "stop": address,
            }
        }
    
    elif action == "set_destination":
        success = bool(address.strip()) and bool(car.navigation.set_destination(address))
        return {
            "result": {
                "success": success,
                "action": "set_destination",
                "destination": address,
            }
        }
    
    return {
        "result": {
            "success": False,
            "action": action,
            "message": "Unknown navigation action.",
        }
    }
