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
        "contact_name": "Anna Kowalska",
        "number_type": "work",
    }


def test_music_node_toggles_playing_state():
    car = CarSystem()

    result = music_node({"action": "play_pause", "payload": {}}, car)

    assert result["result"] == {
        "success": True,
        "action": "play_pause",
        "isPlaying": True,
        "currentTrackIndex": 0,
    }
    assert car.music.isPlaying is True # type: ignore


def test_music_node_reports_unknown_track_as_failure():
    car = CarSystem()

    result = music_node(
        {
            "action": "select_track",
            "payload": {"title": "Unknown track"},
        },
        car,
    )

    assert result["result"]["success"] is False


def test_navigation_node_sets_destination():
    car = CarSystem()

    result = navigation_node(
        {
            "action": "set_destination",
            "payload": {"address": "ul. Końcowa 5, Szczecin"},
        },
        car,
    )

    assert result["result"] == {
        "success": True,
        "action": "set_destination",
        "destination": "ul. Końcowa 5, Szczecin",
    }
    assert car.navigation.destination == "ul. Końcowa 5, Szczecin" # type: ignore


def test_navigation_node_rejects_empty_destination():
    car = CarSystem()

    result = navigation_node(
        {
            "action": "set_destination",
            "payload": {"address": "   "},
        },
        car,
    )

    assert result["result"] == {
        "success": False,
        "action": "set_destination",
        "destination": "   ",
    }


def test_navigation_node_rejects_unknown_destination():
    car = CarSystem()

    result = navigation_node(
        {
            "action": "set_destination",
            "payload": {"address": "ul. Nieznana 1, Szczecin"},
        },
        car,
    )

    assert result["result"]["success"] is False


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
        "contact_name": "Anna Kowalska",
        "number_type": "work",
    }
