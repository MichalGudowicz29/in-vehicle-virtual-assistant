import pytest

from CarSystem.navigation_controller import NavigationController


@pytest.mark.parametrize('address', [
    'Ul.Zolnierska47, Szczecin',
    'Żołnierska 47',
    '  ULICA ŻOŁNIERSKA  47 , SZCZECIN  ',
    'zolnierska47',
])
def test_destination_accepts_equivalent_address_formats(address):
    navigation = NavigationController()
    assert navigation.set_destination(address)
    assert navigation.destination == 'ul. Żołnierska 47, Szczecin'


def test_search_matches_fragments_without_changing_route():
    navigation = NavigationController()
    assert [p['address'] for p in navigation.search_places('niers 47')] == [
        'ul. Żołnierska 47, Szczecin',
    ]
    assert navigation.destination == ''
    assert len(navigation.routePoints) == 1


def test_numbers_and_suffixes_are_not_partial_matches():
    navigation = NavigationController()
    navigation._places['ul. żołnierska 147, szczecin'] = {
        'address': 'ul. Żołnierska 147, Szczecin', 'lat': 53.43, 'lon': 14.55,
    }
    assert [p['address'] for p in navigation.search_places('zolnierska47')] == [
        'ul. Żołnierska 47, Szczecin',
    ]
    assert navigation.search_places('zolnierska 4') == []
    assert navigation.search_places('zolnierska 47a') == []
    assert navigation.get_coordinates('zolnierska') is None
    assert navigation.set_destination('zolnierska47')


@pytest.mark.parametrize('query', ['', '   ', 'ul.', '.*', 'zolnierska99', 'zolnierska47 Warszawa'])
def test_empty_and_unknown_queries_do_not_select_an_address(query):
    navigation = NavigationController()
    assert navigation.search_places(query) == []
    assert navigation.get_coordinates(query) is None


def test_exact_address_ranks_above_fragment_matches_and_resolves_ambiguity():
    navigation = NavigationController()
    navigation._places['ul. nowa żołnierska 47, szczecin'] = {
        'address': 'ul. Nowa Żołnierska 47, Szczecin', 'lat': 53.43, 'lon': 14.55,
    }
    assert [p['address'] for p in navigation.search_places('zolnierska47 Szczecin')] == [
        'ul. Żołnierska 47, Szczecin', 'ul. Nowa Żołnierska 47, Szczecin',
    ]
    assert navigation.set_destination('zolnierska47 Szczecin')
    assert navigation.destination == 'ul. Żołnierska 47, Szczecin'


def test_stop_actions_use_the_same_normalization():
    navigation = NavigationController()
    assert navigation.add_stop('Stacyjna10')
    assert navigation.stops[0]['address'] == 'ul. Stacyjna 10, Szczecin'
    assert navigation.remove_stop('UL.STACYJNA10,SZCZECIN')
    assert navigation.stops == []
