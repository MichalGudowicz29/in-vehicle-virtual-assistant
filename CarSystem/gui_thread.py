"""Run controller methods on the GUI thread, also when the voice worker calls them.

Controllers own Qt state shown by QML, so it may change only on the thread that owns the
controller. A call from the voice thread is marshalled with a blocking queued signal; the
caller waits and receives the real return value (or exception).
"""

from functools import wraps

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot


class _Invoker(QObject):
    request = Signal(object)

    def __init__(self, parent):
        super().__init__(parent)
        self.request.connect(self._run, Qt.ConnectionType.BlockingQueuedConnection)

    @Slot(object)
    def _run(self, call):
        call()


def on_gui_thread(method):
    @wraps(method)
    def wrapper(self, *args):
        if QThread.currentThread() == self.thread():
            return method(self, *args)
        invoker = getattr(self, '_gui_invoker', None)
        if invoker is None:
            raise RuntimeError(f'{type(self).__name__} must call init_gui_thread() in __init__.')
        outcome = {}

        def call():
            try:
                outcome['result'] = method(self, *args)
            except Exception as error:  # re-raised in the calling thread
                outcome['error'] = error

        invoker.request.emit(call)
        if 'error' in outcome:
            raise outcome['error']
        return outcome['result']
    return wrapper


def init_gui_thread(controller: QObject) -> None:
    """Create the invoker in the controller's (GUI) thread; call from the controller's __init__."""
    controller._gui_invoker = _Invoker(controller)
