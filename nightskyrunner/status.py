import logging
import threading
from enum import Enum
from datetime import datetime
from typing import overload, Optional, Callable, Any, Union, Literal
from . import shared_memory as sm

class _Timed:
    def __init__(self)->None:
        self._started: Optional[datetime] = None

    def start(self) -> None:
        self._started = datetime.now()

    def reset(self) -> None:
        self._started = None

    def duration(self) -> Optional[str]:
        if not self._started:
            return None
        d = datetime.now() - self._started
        return str(d)


class StatusState(Enum):
    running = (0,)
    starting = (1,)
    off = (2,)
    error = (3,)


LogLevel = Literal[  
    logging.DEBUG, 
    logging.INFO,
    logging.NOTSET,
    logging.WARNING,
    logging.ERROR,
    logging.CRITICAL,
]
"""
Union of all logging levels (DEBUG, INFO, NOTSET,
WARNING, ERROR and CRITICLA)
"""


def _set_sm(method):
    @wraps(method)
    def _impl(self, *args, **kwargs):
        method(args, kwargs)
        self._sm_item.set(copy.deepcopy(self))

    return _impl


class Status(_Timed):

    sm_key = "status"
    callbacks: dict[LogLevel, list[Callable[[str,str],Any]]] = {}
    _callbacks_lock = threading.Lock()

    def __init__(
        self,
        name: str,
        state_loglevel: dict[StatusState, LogLevel] = {
            StatusState.running: logging.DEBUG,
            StatusState.starting: logging.INFO,
            StatusState.off: logging.INFO,
            StatusState.error: logging.ERROR,
        },
    ) -> None:
        super().__init__()
        self._name = name
        self._state_loglevel = state_loglevel
        self._entries: dict[str, str] = {}
        self._state: StatusState.off
        self._sm_item = sm.root().sub(self.sm_key, exists_ok=True).item(
            self._name, exists_ok=False
        )
        self.start()

    def _callbacks(self, message: str, loglevel: LogLevel) -> None:
        try:
            callbacks_ = self.callbacks[loglevel]
        except KeyError:
            return
        for callback in callbacks_:
            with self._callbacks_lock:
                callback(self._name, message)

    @_set_sm
    def _set_state(self, state: StatusState) -> None:
        if self._state == state:
            return
        if state == StatusState.starting:
            self.start()
        elif state in (StatusState.off, StatusState.error):
            self.reset()
        if state == StatusState.running:
            self._set_value(f"running for {self.duration()}", loglevel=None)
        status_change = f"{self._state}.name->{state}.name"
        self._state = state
        try:
            loglevel = self._state_loglevel[state]
        except KeyError:
            return
        self._callbacks(status_change, loglevel)

    @_set_sm
    def _set_value(
        self, key: str, value: str, loglevel: Optional[LogLevel] = None
    ) -> None:
        try:
            previous = self._entries[key]
        except KeyError:
            self._entries[key] = value
            previous = value
        if previous != value and loglevel:
            self._callbacks(f"{key} set to {value}")

    @overload
    def status(self, key: str, value: str, loglevel: Optional[LogLevel] = None) -> None:
        ...

    @overload
    def status(self, state: StatusState) -> None:
        ...

    def status(
        self,
        arg1: Union[str, StatusState],
        arg2: Optional[str] = None,
        loglevel: Optional[LogLevel] = None,
    ) -> None:
        if isinstance(arg1, str):
            if not arg2:
                raise ValueError(
                    "second argument of the value method should be a string"
                    f" (got {type(arg2)})"
                )
            self._set_value(arg1, arg2)
            return
        self._set_state(arg1)
