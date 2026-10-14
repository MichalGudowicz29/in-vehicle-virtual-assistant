from langgraph.graph import END, START, StateGraph

from .nodes.contacts import contacts_node
from .nodes.music import music_node
from .nodes.navigation import navigation_node
from .router import route_node
from .state import HMIState


def build_graph(car):
    graph = StateGraph(HMIState)

    def router_entry(state: HMIState):
        return route_node(state, car)

    def contacts_entry(state: HMIState):
        return contacts_node(state, car)

    def music_entry(state: HMIState):
        return music_node(state, car)

    def navigation_entry(state: HMIState):
        return navigation_node(state, car)

    def unknown_entry(state: HMIState):
        return {
            "result": {
                "success": False,
                "action": state["action"] if "action" in state else None,
                "message": "Unknown intent.",
            }
        }

    def route_key(state: HMIState) -> str:
        if "route" not in state:
            raise ValueError("Router did not produce a route.")
        return state["route"]

    graph.add_node("router", router_entry)
    graph.add_node("contacts", contacts_entry)
    graph.add_node("music", music_entry)
    graph.add_node("navigation", navigation_entry)
    graph.add_node("unknown", unknown_entry)

    graph.add_edge(START, "router")
    graph.add_conditional_edges(
        "router",
        route_key,
        {
            "contacts": "contacts",
            "music": "music",
            "navigation": "navigation",
            "unknown": "unknown",
        },
    )

    for node_name in ("contacts", "music", "navigation", "unknown"):
        graph.add_edge(node_name, END)

    return graph.compile()
