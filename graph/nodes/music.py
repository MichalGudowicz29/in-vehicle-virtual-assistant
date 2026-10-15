from typing import Any

from ..state import HMIState


def music_node(state: HMIState, car: Any) -> dict[str, dict[str, Any]]:
    action = state["action"] if "action" in state else None
    payload = state["payload"] if "payload" in state else {}

    if action == "play_pause":
        requested = car.music.play_pause()
    elif action == "next_track":
        requested = car.music.next_track()
    elif action == "previous_track":
        requested = car.music.previous_track()
    elif action == "select_track":
        requested = car.music.select_track(payload["title"])
    else:
        return {
            "result": {
                "success": False,
                "action": action,
                "message": "Unknown music action.",
            }
        }

    return {
        "result": {
            "success": bool(requested),
            "action": action,
            "isPlaying": car.music.isPlaying,
            "currentTrackIndex": car.music.currentTrackIndex,
        }
    }
