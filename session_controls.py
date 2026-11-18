"""Qt entry points for measuring touch operations without changing controllers."""

from uuid import uuid4

from PySide6.QtCore import QObject, Property, Signal, Slot


ACTIONS = {
    'music': {'play_pause', 'next_track', 'previous_track', 'select_track'},
    'contacts': {'call_contact', 'end_call'},
    'navigation': {'set_destination', 'add_stop', 'remove_stop', 'clear_route'},
}


class SessionControls(QObject):
    userMessageChanged = Signal()

    def __init__(self, car, report, *, touch_enabled=True):
        super().__init__()
        self.car = car
        self.report = report
        self._touch_enabled = touch_enabled
        self._user_message = ''

    @Property(str, notify=userMessageChanged)
    def userMessage(self):
        return self._user_message

    @Slot(str)
    def showUserMessage(self, message):
        if message != self._user_message:
            self._user_message = message
            self.userMessageChanged.emit()

    @Property(bool, constant=True)
    def touchEnabled(self):
        return self._touch_enabled

    @Slot(str)
    def recordTouch(self, action):
        if self._touch_enabled:
            self.report.emit('touch', action=action)

    @Slot(str)
    def recordScreen(self, screen):
        self.report.emit('screen_change', screen=screen)

    @Slot(str, str, 'QVariantList', result=bool)
    def performTouch(self, domain, action, args):
        if not self._touch_enabled:
            return False
        run_id = uuid4().hex
        name = f'{domain}.{action}'
        self.report.emit('touch_start', run_id=run_id, action=name, arguments=args)
        try:
            if action not in ACTIONS.get(domain, set()):
                raise ValueError(f'Unknown touch action: {name}')
            result = getattr(getattr(self.car, domain), action)(*args)
        except Exception as error:
            self.report.emit('touch_end', run_id=run_id, action=name, success=False, error=str(error))
            return False
        success = result is not False
        self.report.emit('touch_end', run_id=run_id, action=name, success=success)
        return success
