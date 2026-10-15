from CarSystem.contact_controller import ContactController


def test_adds_contact_with_two_numbers():
    contacts = ContactController()

    contacts.set_contacts([
        {
            "name": "Piotr Testowy",
            "mobile": "501111111",
            "work": "221111111",
        }
    ])

    contact = contacts.contacts[-1]
    assert contact["mobile"] == "501111111"
    assert contact["work"] == "221111111"


def test_adds_contact_with_one_number():
    contacts = ContactController()

    contacts.set_contacts([
        {
            "name": "Anna Testowa",
            "mobile": "502222222",
        }
    ])

    contact = contacts.contacts[-1]
    assert contact == {
        "name": "Anna Testowa",
        "mobile": "502222222",
    }


def test_calls_selected_number_for_contact():
    contacts = ContactController()
    called_numbers = []
    calling_states = []
    contacts.callingRequested.connect(called_numbers.append)
    contacts.isCallingChanged.connect(
        lambda: calling_states.append(
            (contacts.isCalling, contacts.currentContactName)
        )
    )

    contacts.set_contacts([
        {
            "name": "Piotr Testowy",
            "mobile": "501111111",
            "work": "221111111",
        }
    ])

    contacts.call_contact("Piotr Testowy", "work")

    assert called_numbers == ["221111111"]
    assert calling_states[0] == (True, "Piotr Testowy")
    assert contacts.isCalling is True
    assert contacts.currentContactName == "Piotr Testowy"

    contacts.end_call()

    assert contacts.isCalling is False
    assert contacts.currentContactName == ""


def test_calling_missing_number_returns_failure():
    contacts = ContactController()

    assert contacts.call_contact("Robert Lewandowski", "work") is False
