import logging
import threading
import copy
from functools import wraps
from enum import Enum
from datetime import datetime
from typing import Optional, Callable, Any
from .shared_memory import SharedMemory, MultiPDict


class Timed:
    """
    Used for tracking a duration.
    """

    def __init__(self) -> None:
        self._started: Optional[datetime] = None

    def start(self) -> None:
        """
        Starting the counter.
        """
        self._started = datetime.now()

    def reset(self) -> None:
        """
        Setting back the counter to None
        """
        self._started = None

    def duration(self) -> Optional[str]:
        """
        Returning a string expressing the
        time passed since the last call
        to 'start' (or None if 'reset'
        has been called in the meantime)
        """
        if not self._started:
            return None
        d = datetime.now() - self._started
        return str(d)


class State(Enum):
    """
    Possible status states
    """

    running = (0,)
    starting = (1,)
    stopping = (2,)
    off = (3,)
    error = (4,)


class Level(Enum):
    """
    Enumeration of levels, to be used
    for status callbacks
    """

    debug = (logging.DEBUG,)
    info = (logging.INFO,)
    notset = (logging.NOTSET,)
    warning = (logging.WARNING,)
    error = (logging.ERROR,)
    critical = (logging.CRITICAL,)


def _set_sm(method):
    # 'self' is an instance of Status.
    # (i.e. 'method' is a method of Status
    #        and _sm_item is an attribute of
    #        Status)
    # This decorator ensure that the instance
    # of status is saved to the shared memory
    # upon the call to method.
    @wraps(method)
    def _impl(self, *args, **kwargs):
        method(self, *args, **kwargs)
        sm: MultiPDict = SharedMemory.get(self.sm_key)
        sm[self._name] = self

    return _impl


class NoSuchStatusError(Exception):
    """
    Exception to be thrown when a thread attempt
    to retrieve a non existing instance of status.
    """

    def __init__(self, name: str) -> None:
        self._name = name

    def __str__(self) -> str:
        return str(
            f"not status named {self._name}" "could be retrieved from the shared memory"
        )


Callback = Callable[[str, str], None]
"""
Callback for Status. First argument is the status name,

the second an arbitrary string.
"""
Callbacks = list[Callback]


class Status(Timed):
    """
    Object for tracking the status state and related
    message / values of a Runner.

    Instances of status stores themselves automatically
    in the shared memory, so that they can be accessed
    by different threads asynchronously:

    ```python
    # reads the shared memory Item
    status: Status = Status.retrieve("status_name")
    ```

    An instance of Status is:
    - a state (e.g. running, off)
    - a message: a single arbitrary string
    - values: a dictionay string to string

    Class level callbacks can be added, e.g.

    ```python
    def print_level(level):
        print(level)

    Status.set_callback(print_level, [level.info, level.warning])
    status = Status("runner1")
    status.message("instance of runner1 created", level.info)
    # level.info printed
    ```

    Status is a subclass of Timed, which is used to measure for how
    long the state of an instance of Status has been 'running'.

    ```python
    d = status.duration()
    # d is None if the current state of status is not 'running',
    # a string otherwise
    ```

    Args:
      name: arbitrary string, allowing to retrieve
        the instance of status from the shared memory
      state_level: a dictionary mapping a status state
        to a level, e.g. 'off' mapping to 'error' means
        the 'error' callbacks will be called when the
        state switches to the level 'off'
    """

    sm_key = "status"
    _callbacks: dict[Level, Callbacks] = {}
    _callbacks_lock = threading.Lock()

    def __init__(
        self,
        name: str,
        state_level: dict[State, Level] = {
            State.running: Level.debug,
            State.starting: Level.info,
            State.off: Level.info,
            State.error: Level.error,
        },
    ) -> None:
        super().__init__()  # Timed
        self._name = name
        self._state_level = state_level
        self._entries: dict[str, str] = {}
        self._state = State.off
        self._error: Optional[str] = None
        self._message: Optional[str] = None
        self.start()

    @property
    def name(self) -> str:
        return self._name

    def get_state(self) -> State:
        return self._state

    @classmethod
    def set_callback(cls, level: Level, callback: Callback) -> None:
        """
        Add a callback that will be called when a message or value
        of the specified level are set or modified.
        """
        try:
            cls._callbacks[level].append(callback)
        except KeyError:
            cls._callbacks[level] = [callback]

    @classmethod
    def retrieve(cls, name: str) -> "Status":
        """
        Returns a deep copy of the related instance
        of Status (or throws a NotSuchStatusError)
        """
        sm: MultiPDict = SharedMemory.get(cls.sm_key)
        try:
            instance: "Status" = sm[name]
        except KeyError:
            raise NoSuchStatusError(name)
        return copy.deepcopy(instance)

    def _call_callbacks(self, message: str, level: Level) -> None:
        try:
            callbacks_ = self._callbacks[level]
        except KeyError:
            return
        for callback in callbacks_:
            with self._callbacks_lock:
                callback(self._name, message)

    def get(self) -> dict[str, Any]:
        """
        Returns a dictionary representation of this status.
        """
        d: dict[str, Any] = {
            "name": self._name,
            "entries": self._entries,
            "message": self._message,
            "state": self._state,
            "running_for": self.duration(),
        }
        return d

    @_set_sm
    def state(self, state: State, error: Optional[str] = None) -> None:
        """
        Set the current state. If it changes from the previous state,
        callbacks are called.

        Args:
          state: the new status
          error: the error message to be set. Ignored if state is not
            State.error.
        """
        if state != State.error:
            self._error = None
        if self._state == state:
            return
        if state == state.starting:
            self.start()
        elif state in (state.off, state.error):
            self.reset()
            if state == state.error:
                self._error = error
        if state == state.running:
            self._value("running for", str(self.duration()), level=None)
        status_change = f"{self._state}.name->{state}.name"
        if state == State.error:
            status_change = f"{status_change} (self._error)"
        self._state = state
        try:
            level = self._state_level[state]
        except KeyError:
            return
        self._call_callbacks(status_change, level)

    def _value(self, key: str, value: str, level: Optional[Level] = None) -> None:
        try:
            previous = self._entries[key]
        except KeyError:
            self._entries[key] = value
            previous = value
        self._entries[key] = value
        if previous != value and level:
            self._call_callbacks(f"{key} set to {value}", level)

    @_set_sm
    def value(self, key: str, value: str, level: Optional[Level] = None) -> None:
        """
        Update the value for the specified key. If level is not None,
        callbacks are called.
        """
        self._value(key, value, level=level)

    @_set_sm
    def message(
        self,
        msg: str,
        level: Optional[Level] = None,
    ) -> None:
        """
        Set the status's message, overwriting the previous message,
        if any. Callbacks related to the level are called.
        """
        self._message = msg
        if level:
            self._call_callbacks(msg, level)
