"""
Module defining the Status class.
"""

import copy
import logging
import threading
import time
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, TypedDict

from .shared_memory import DictProxy, SharedMemory


class Timed:
    """
    Used for tracking a duration.
    """

    def __init__(self) -> None:
        self._started: Optional[float] = None

    def start(self) -> None:
        """
        Starting the counter.
        """
        self._started = time.time()

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
        d = time.time() - self._started
        return str(_format_seconds(d))


def _int_to_enum(enum_type: Type[Enum]) -> Dict[Any, Any]:
    return {enum.value: enum for enum in enum_type}


class State(Enum):
    """
    Possible status states
    """

    running = 0
    starting = 1
    stopping = 2
    off = 3
    error = 4


int_to_state = _int_to_enum(State)
"""
Dictionary which keys are integer, and values corresponding
State, e.g. '4'->State.Error.
"""


class Level(Enum):
    """
    Enumeration of levels, to be used
    for status callbacks
    """

    debug = logging.DEBUG
    info = logging.INFO
    notset = logging.NOTSET
    warning = logging.WARNING
    error = logging.ERROR
    critical = logging.CRITICAL


def _set_sm(method):
    # 'self' is an instance of Status.
    # (i.e. 'method' is a method of Status
    #        and _sm_item is an attribute of
    #        Status)
    # This decorator ensures that the instance
    # of status is saved to the shared memory
    # upon the call to method.
    @wraps(method)
    def _impl(self, *args: Any, **kwargs: Any) -> None:
        method(self, *args, **kwargs)
        sm: DictProxy = SharedMemory.get(self.sm_key)
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
            f"not status named {self._name} could be retrieved from the shared memory"
        )


Callback = Callable[["Status", str], None]
"""
Callback for Status. First argument is the status instance,

the second an arbitrary string.
"""
Callbacks = List[Callback]
"""
A List of status Callback
"""


def _seconds_to_DHMS(duration: float) -> Tuple[int, int, int, int]:
    # Convert a duration in seconds, to a tuple corresponding to the
    # corresponding duration in terms of days, hours, minutes and
    # seconds.
    duration_ = int(duration + 0.5)
    m, s = divmod(duration_, 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)
    return (d, h, m, s)


def _format_seconds(duration: Optional[float]) -> str:
    # convert a duration in seconds to a string
    # expressing the duration in the format
    # X days X hours X minutes X seconds.
    if not duration:
        return ""
    d, h, m, s = _seconds_to_DHMS(duration)

    if (d, h, m, s) == (0, 0, 0, 0):
        return str(duration)

    def _f(value: int, label: str) -> str:
        if value != 0:
            return str(value) + label
        return ""

    return "".join(
        [
            _f(v, l)
            for v, l in zip(
                (d, h, m, s),
                (" days ", " hours ", " minutes ", " seconds"),
            )
        ]
    )


class ErrorDict(TypedDict, total=False):
    message: Optional[str]
    started: Optional[str]
    previous: Optional[str]
    previous_started: Optional[str]


class _EManager:
    # Convenience class for managing an error message.
    # It keeps in memory not only the current error message
    # (if any) but also info related to the previous error message.
    # It keeps also track of the time at which the error occured.
    # There will be two subclasses: for error
    # and for issues
    def __init__(self) -> None:
        self._current_error: Optional[str] = None
        self._previous_error: Optional[str] = None
        self._current_error_time: Optional[float] = None
        self._previous_error_time: Optional[float] = None

    def _update(self, error: Optional[str]) -> None:
        if error:
            if error == self._current_error:
                return
            else:
                if self._current_error is not None:
                    self._previous_error = self._current_error
                    self._previous_error_time = self._current_error_time
                if error:
                    self._current_error = error
                    self._current_error_time = time.time()
        else:
            if self._current_error is not None:
                self._previous_error = self._current_error
                self._previous_error_time = self._current_error_time
            self._current_error = None
            self._current_error_time = None

    def error_message(self) -> Optional[str]:
        # returns the current error message
        # (if any, None otherwise)
        return self._current_error

    def get(self) -> ErrorDict:
        # returns a dictionary which
        # contents describes the
        # current and previous error,
        # as well as how long ago
        # they occured.
        r = ErrorDict()
        if self._current_error:
            r["message"] = self._current_error
            if self._current_error_time:
                ago = _format_seconds(time.time() - self._current_error_time)
                r["started"] = f"{ago} ago"
        if self._previous_error:
            r["previous"] = self._previous_error
            if self._previous_error_time:
                ago = _format_seconds(time.time() - self._previous_error_time)
                r["previous_started"] = f"{ago} ago"
        return r


class _ErrorManager(_EManager):
    # subclass of _Emanager for error
    # (a runner having an error means a runner
    # which iterate function threw an Exception)
    def __init__(self) -> None:
        super().__init__()

    def update(self, state: State, error: Optional[str]) -> None:
        if state == State.error:
            self._update(error)
        else:
            self._update(None)


class _IssueManager(_EManager):
    # subclass of _Emanager for issue
    # (a runner having an issue means a runner
    # iterates function exited correctly, but
    # the runner experienced some issue which
    # may degrade its service.
    # The runner indicates issues by calling
    # in its iteration function something like:
    # ```
    # self._status.set_issue("detected an issue")
    # ```
    def __init__(self) -> None:
        super().__init__()

    def update(self, issue: Optional[str]) -> None:
        self._update(issue)


class RunnerStatusDict(TypedDict, total=False):
    """
    For serialization of status date specific
    to each runner type.
    """

    ...


class StatusDict(TypedDict, total=False):
    """
    For serialization of all the data
    related to an instance of Status
    """

    name: str
    runner_class: str
    entries: Optional[RunnerStatusDict]
    activity: Optional[str]
    state: str
    running_for: Optional[str]
    error: ErrorDict
    issue: ErrorDict


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
    - an activity: an arbitrary string describing what
       the related runner is doing

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

    Developers of [runner.Runner]() can iteract with
    the status attribute of the runner, e.g.

    ```python
    def iterate(self):
      # set the activity of the status, and
      # save the status in the shared memory.
      self._status.activity("entering iterate function")
    ```

    Arguments:
      name: arbitrary string, allowing to retrieve
        the instance of status from the shared memory
      state_level: a dictionary mapping a status state
        to a level, e.g. 'off' mapping to 'error' means
        the 'error' callbacks will be called when the
        state switches to the level 'off'
    """

    sm_key = "status"
    _callbacks: Dict[Level, Callbacks] = {}
    _callbacks_lock = threading.Lock()

    def __init__(self, name: str, runner_class: str) -> None:
        super().__init__()  # Timed
        self._name = name
        self._runner_class: str = runner_class
        self._entries: Optional[RunnerStatusDict] = None
        self._state = State.off
        self._error = _ErrorManager()
        self._issue = _IssueManager()
        self._activity: Optional[str] = None
        self.start()
        self._save()

    @property
    def name(self) -> str:
        return self._name

    def get_state(self) -> State:
        return self._state

    @classmethod
    def delete(cls, name: str) -> None:
        """
        delete the status from the shared memory
        """
        sm: DictProxy = SharedMemory.get(cls.sm_key)
        try:
            del sm[name]
        except KeyError:
            pass

    @classmethod
    def clear_all(cls) -> None:
        """
        delete all status from the shared memory
        """
        sm: DictProxy = SharedMemory.get(cls.sm_key)
        names = list(sm.keys())
        for name in names:
            cls.delete(name)

    @classmethod
    def retrieve(cls, name: str) -> "Status":
        """
        Returns a deep copy of the related instance
        of Status (or throws a NotSuchStatusError)
        """
        sm: DictProxy = SharedMemory.get(cls.sm_key)
        try:
            instance: "Status" = sm[name]
        except KeyError:
            raise NoSuchStatusError(name)
        return copy.deepcopy(instance)

    @classmethod
    def known_status(cls) -> List[str]:
        """
        Returns the name of all the status
        currently stored in the shared memory
        """
        sm: DictProxy = SharedMemory.get(cls.sm_key)
        return list(sm.keys())

    @classmethod
    def retrieve_all(cls) -> List["Status"]:
        sm: DictProxy = SharedMemory.get(cls.sm_key)
        return [cls.retrieve(name) for name in sm.keys()]

    def get(self) -> StatusDict:
        """
        Returns a dictionary representation of this status.
        """
        return StatusDict(
            name=self._name,
            runner_class=self._runner_class,
            entries=self._entries,
            activity=self._activity,
            state=self._state.name,
            running_for=self.duration(),
            error=self._error.get(),
            issue=self._issue.get(),
        )

    def __str__(self) -> str:
        return str(self.get())

    @_set_sm
    def set_issue(self, issue: str) -> None:
        self._issue.update(issue)

    @_set_sm
    def remove_issue(self) -> None:
        self._issue.update(None)

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
        self._error.update(state, error)
        if self._state == state:
            return
        if state == state.starting:
            self.start()
        if self._state == state.error and state == state.running:
            self.start()
        elif state in (state.off, state.error):
            self.reset()
        status_change = f"{self._state.name}->{state.name}"
        if state == State.error:
            status_change = f"{status_change} ({self._error.error_message()})"
        self._state = state

    @_set_sm
    def _save(self) -> None: ...

    @_set_sm
    def entries(self, entries: RunnerStatusDict):
        self._entries = entries

    @_set_sm
    def activity(
        self,
        activity: str,
    ) -> None:
        """
        Set the status's activity
        """
        self._activity = activity


class StateError(Exception): ...


def wait_for_status(
    instance_name: str,
    desired_status: State,
    timeout: float = 1.0,
    time_sleep: float = 0.005,
) -> bool:
    """
    Wait for the status of the corresponding runner to change to the specified state.
    Return True, when the status switches to the desired state.
    Otherwise raise a [StateError](), when timeout is reached.

    If there is no status of the specified name created before the timeout, a
    [nightskyrunner.status.NoSuchStatusError](NoSuchStatusError) is raised.

    Args:
      instance_name: name of the runner
      desired_status: the status we believe the runner will switch to
      timeout: in seconds
      time_sleep: in seconds, sleeping time between each status check

    Returns:
      True

    Raises:
      [NoSuchStatusError]()
      [StateError]()
    """
    timestart = time.time()
    while True:
        if time.time() - timestart > timeout:
            raise NoSuchStatusError(instance_name)
        try:
            Status.retrieve(instance_name)
        except NoSuchStatusError:
            pass
        else:
            break
    timestart = time.time()
    current_state = Status.retrieve(instance_name).get()["state"]
    while current_state != desired_status.name:
        if time.time() - timestart > timeout:
            break
        time.sleep(time_sleep)
        current_state = Status.retrieve(instance_name).get()["state"]
    if current_state != desired_status.name:
        raise StateError(
            f"{instance_name} did not switch to {desired_status.name} within {timeout} seconds"
        )
    return True
