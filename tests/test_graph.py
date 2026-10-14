from CarSystem.car_system import CarSystem

from graph.builder import build_graph
from graph.nodes.contacts import contacts_node
from graph.nodes.music import music_node
from graph.nodes.navigation import navigation_node
from graph.router import route_node


def test_route_node_selects_domain_from_intent():
    car = CarSystem()

    result = route_node({"intent": "contacts"}, car)

    assert result["route"] == "contacts"


def test_contacts_node_calls_selected_number():
    car = CarSystem()

    result = contacts_node(
        {
            "action": "call_contact",
            "payload": {
                "name": "Anna Kowalska",
                "number_type": "work",
            },
        },
        car,
    )

    assert result["result"] == {
        "success": True,
        "action": "call_contact",
    }


def test_music_node_toggles_playing_state():
    car = CarSystem()

    result = music_node({"action": "play_pause", "payload": {}}, car)

    assert result["result"] == {
        "success": True,
        "action": "play_pause",
    }
    assert car.music.isPlaying is True


def test_navigation_node_sets_destination():
    car = CarSystem()

    result = navigation_node(
        {
            "action": "set_destination",
            "payload": {"address": "Szczecin"},
        },
        car,
    )

    assert result["result"] == {
        "success": True,
        "action": "set_destination",
    }
    assert car.navigation.destination == "Szczecin"


def test_build_graph_routes_contact_action():
    car = CarSystem()
    graph = build_graph(car)

    result = graph.invoke(
        {
            "intent": "contacts",
            "action": "call_contact",
            "payload": {
                "name": "Anna Kowalska",
                "number_type": "work",
            },
        }
    )

    assert result["route"] == "contacts"
    assert result["result"] == {
        "success": True,
        "action": "call_contact",
    }
