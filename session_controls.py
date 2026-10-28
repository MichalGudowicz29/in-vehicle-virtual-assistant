"""Qt entry points for measuring touch operations without changing controllers."""

from uuid import uuid4

from PySide6.QtCore import QObject, Slot


ACTIONS = {
    'music': {'play_pause', 'next_track', 'previous_track', 'select_track'},
    'contacts': {'call_contact', 'end_call'},
    'navigation': {'set_destination', 'add_stop', 'remove_stop', 'clear_route'},
}


class SessionControls(QObject):
    def __init__(self, car, report):
        super().__init__()
        self.car = car
        self.report = report

    @Slot(str)
    def recordTouch(self, action):
        self.report.emit('touch', action=action)

    @Slot(str)
    def recordScreen(self, screen):
        self.report.emit('screen_change', screen=screen)

    @Slot(str, str, 'QVariantList', result=bool)
    def performTouch(self, domain, action, args):
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
