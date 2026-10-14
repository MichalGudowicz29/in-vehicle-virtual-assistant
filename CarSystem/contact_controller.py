from PySide6.QtCore import Q_ARG, QMetaObject, QObject, Property, QThread, Qt, Signal, Slot


class ContactController(QObject):
    contactsChanged = Signal()
    callingRequested = Signal(str)

    def __init__(self):
        super().__init__()
        self._contacts = [
            {
                "name": "Robert Lewandowski",
                "mobile": "501234567",
            },
            {
                "name": "Anna Kowalska",
                "mobile": "502345678",
                "work": "223456789",
            },
            {
                "name": "Jan Nowak",
                "work": "224567890",
            },
        ]
        self._current_contact_index = -1

    @Property(list, notify=contactsChanged)
    def contacts(self):
        return self._contacts

    @Slot(str, str)
    def call_contact(self, contact_name: str, contact_type: str):
        contact = next((
            contact
            for contact in self._contacts
            if contact["name"] == contact_name
        ), None)
        
        if QThread.currentThread() != self.thread():
            QMetaObject.invokeMethod(
                self,
                "_call_contact",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(str, contact_name),
                Q_ARG(str, contact_type),
            )
            return True

        return self._call_contact(contact_name, contact_type)

    @Slot(str, str)
    def _call_contact(self, contact_name: str, contact_type: str = "mobile"):
        for contact in self._contacts:
            if contact["name"] == contact_name:
                self.callingRequested.emit(contact[contact_type])
                self._current_contact_index = self._contacts.index(contact)
                return True
        return False

    @Slot(list)
    def set_contacts(self, contacts: list):
        if QThread.currentThread() != self.thread():
            QMetaObject.invokeMethod(
                self,
                "_set_contacts",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(list, contacts),
            )
            return

        self._set_contacts(contacts)

    @Slot(list)
    def _set_contacts(self, contacts: list):
        self._contacts.extend(contacts)
        self.contactsChanged.emit()
        print(f"Set contacts to {contacts}")
