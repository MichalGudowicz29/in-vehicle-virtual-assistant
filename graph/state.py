from typing import Any, TypedDict


class HMIState(TypedDict, total=False):
    intent: str
    route: str
    action: str
    payload: dict[str, Any]
    result: dict[str, Any]
