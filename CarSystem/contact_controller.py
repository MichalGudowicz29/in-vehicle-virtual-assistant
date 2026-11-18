from PySide6.QtCore import QObject, Property, Signal, Slot

from .gui_thread import init_gui_thread, on_gui_thread
from .matching import all_terms_match, tokens

# Words around a name in a spoken command ("zadzwoń do pana Roberta").
_QUERY_STOPWORDS = {"do", "z", "ze", "pan", "pana", "pani", "panem", "mnie", "zadzwon", "polacz"}


class ContactController(QObject):
    """Contact list and a simulated phone call (no real telephony)."""
    contactsChanged = Signal()
    callingRequested = Signal(str)   # dialled number
    isCallingChanged = Signal()

    def __init__(self):
        super().__init__()
        init_gui_thread(self)
        self._contacts = [
            {"name": "Robert Lewandowski", "mobile": "501234567"},
            {"name": "Anna Kowalska", "mobile": "502345678", "work": "223456789"},
            {"name": "Jan Nowak", "work": "224567890"},
        ]
        self._current_contact_index = -1
        self._isCalling = False

    @Property(list, notify=contactsChanged)
    def contacts(self):
        return self._contacts

    @Property(bool, notify=isCallingChanged)
    def isCalling(self):
        return self._isCalling

    @Property(str, notify=isCallingChanged)
    def currentContactName(self):
        if self._current_contact_index < 0:
            return ""
        return self._contacts[self._current_contact_index]["name"]

    def find_contacts(self, query: str) -> list[dict]:
        """Contacts whose name matches every word of a spoken name ("Roberta" -> Robert Lewandowski)."""
        terms = [term for term in tokens(query) if term not in _QUERY_STOPWORDS]
        exact = [c for c in self._contacts if tokens(c["name"]) == terms]
        return exact or [c for c in self._contacts if all_terms_match(terms, tokens(c["name"]))]

    @Slot()
    @on_gui_thread
    def end_call(self):
        self._current_contact_index = -1
        self._isCalling = False
        self.isCallingChanged.emit()

    @Slot(str, str, result=bool)
    @on_gui_thread
    def call_contact(self, contact_name: str, contact_type: str):
        for index, contact in enumerate(self._contacts):
            if contact["name"] == contact_name:
                if contact_type not in contact:
                    return False
                self._current_contact_index = index
                self._isCalling = True
                self.isCallingChanged.emit()
                self.callingRequested.emit(contact[contact_type])
                return True
        return False

    @Slot(list)
    @on_gui_thread
    def set_contacts(self, contacts: list):
        self._contacts.extend(contacts)
        self.contactsChanged.emit()
