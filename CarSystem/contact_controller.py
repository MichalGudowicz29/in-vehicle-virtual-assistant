from PySide6.QtCore import Q_ARG, Q_RETURN_ARG, QMetaObject, QObject, Property, QThread, Qt, Signal, Slot


class ContactController(QObject):
    contactsChanged = Signal()
    callingRequested = Signal(str)
    isCallingChanged = Signal()

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
        self._isCalling = False

    @Property(list, notify=contactsChanged)
    def contacts(self):
        return self._contacts
    
    @Property(bool, notify=isCallingChanged)
    def isCalling(self):
        return self._isCalling
    
    @Slot()
    def end_call(self):
        if QThread.currentThread() != self.thread():
            QMetaObject.invokeMethod(
                self,
                "_end_call",
                Qt.ConnectionType.QueuedConnection,
            )
            return

        self._end_call()
        
    @Slot()
    def _end_call(self):
        self._current_contact_index = -1
        self._isCalling = False
        self.isCallingChanged.emit()
        
    @Property(str, notify=isCallingChanged)
    def currentContactName(self):
        if self._current_contact_index < 0:
            return ""
        return self._contacts[self._current_contact_index]["name"]

    @Slot(str, str, result=bool)
    def call_contact(self, contact_name: str, contact_type: str):
        contact = next((
            contact
            for contact in self._contacts
            if contact["name"] == contact_name
        ), None)
        
        if QThread.currentThread() != self.thread():
            return QMetaObject.invokeMethod(
                self,
                "_call_contact",
                Qt.ConnectionType.BlockingQueuedConnection,
                Q_RETURN_ARG(bool),
                Q_ARG(str, contact_name),
                Q_ARG(str, contact_type),
            )

        return self._call_contact(contact_name, contact_type)

    @Slot(str, str, result=bool)
    def _call_contact(self, contact_name: str, contact_type: str = "mobile"):
        for contact in self._contacts:
            if contact["name"] == contact_name:
                if contact_type not in contact:
                    return False

                self._current_contact_index = self._contacts.index(contact)
                self._isCalling = True
                self.isCallingChanged.emit()
                self.callingRequested.emit(contact[contact_type])
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
