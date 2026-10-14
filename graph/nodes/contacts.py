from typing import Any

from ..state import HMIState


def contacts_node(state: HMIState, car: Any) -> dict[str, dict[str, Any]]:
    payload = state["payload"] if "payload" in state else {}
    requested = car.contacts.call_contact(
        payload["name"],
        payload["number_type"],
    )

    return {
        "result": {
            "success": bool(requested),
            "action": "call_contact",
        }
    }
