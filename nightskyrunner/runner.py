"""
Module defining the class Runner (and subclasses ThreadRunner and ProcessRunner).
A Runner manages a thread (or a process) which calls at its given frequency a custom "iterate"
method ('custom': developpers create subclasses of Runner implementing this method).
"""

import time
import threading
from typing import Iterable, Optional, Callable
from functools import wraps
from multiprocessing import Process, Value
from .status import Status, State, Level
from . import configcheck
from .config_getter import ConfigGetter
from .shared_memory import MultiPDict, MpValue, SharedMemory


def manage_error(method):
    """
    Decorator for Runner's method.
    When any of the method raise an Exception, this
    Exception is caught and the state of the
    Runner switches to "error".
    """

    @wraps(method)
    def _impl(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except Exception as e:
            self._status.state(State.error, f"{type(e)}: {e}")

    return _impl


class _Sleeper:
    """
    For enforcing a desired frequency.

    Usage:

    ```
    sleeper = _Sleeper(10.)
    while True:
        # this loop will run
        # at 10Hz
        sleeper.wait()
    ```

    Args:
      frequency: the desired frequency
      interrupts: the wait method will call all the
          'interrupt' callables (if any), and if any returns True,
          the wait method exits early.
      core_frequency: frequency at which the wait method
          calls the 'interrupt' callables
    """

    def __init__(
        self,
        frequency: float,
        interrupts: Iterable[Callable[[], bool]],
        core_frequency: float,
    ) -> None:
        self._period = 1.0 / frequency
        self._previous: Optional[float] = None
        self._interrupts = interrupts
        self._core_frequency = core_frequency

    def wait(self):
        """
        Wait the time required to enforce the desired frequency,
        except if any of the 'interrupt' callable returns True
        """
        if self._previous is None:
            self._previous = time.time() - self._period
        while time.time() - self._previous < self._period:
            for interrupt in self._interrupts:
                if interrupt():
                    self._previous = time.time()
                    return
            time.sleep(1.0 / self._core_frequency)
        self._previous = time.time()


# TODO: use class decorator to decorate all method with "manage_error"
class Runner(_Sleeper):
    """
    A Runner manages a thread (ThreadRunner virtual subclass) or a process
    (ProcessRunner virtual subclass) which call at its given frequency
    an 'iterate' method (to be implemented by concrete subclasses).

    An instance of Runner encapsulate an instance of Status, which
    it uses to inform the external world of its status. The instance
    of status can be retrieved by using the Runner's name:

    ```
    # name is the string that has been passed as argument to
    # the runner's constructor.
    status = Status.retrieve(name)
    ```

    Args:
      name: arbitrary name of the runner. Can be used to retrieve's the
        runners' status
      config_getter: instance in charge to return the runner's configuration
        dictionary (can be used in the 'iterate' method)
      frequency: frequency at which the runner will call the 'iterate' method
      interrupts: if any interrupt returns True (and for as long the interrupt
        returns True), there will be no wait between calls to 'iterate'. If
        an interrupt returns True during the wait, the wait is interrupted.
        Expected usage: If the frequency is low, an instance of runner may take a
        long time to exit after a call to the 'stop' method. An interrupt allows
        for shorter this time
      core_frequency: frequency at which interrupts will be called.
    """

    def __init__(
        self,
        name: str,
        config_getter: ConfigGetter,
        frequency: float,
        interrupts: Iterable[Callable[[], bool]] = [],
        core_frequency: float = 200.0,
    ) -> None:
        _Sleeper.__init__(self, frequency, interrupts, core_frequency)
        self._status = Status(name)
        self._config_getter = config_getter

    @property
    def name(self) -> str:
        """
        the name of the Runner (as passed as argument
        to the constructor)
        """
        return self._status.name

    @manage_error
    def start(self):
        """
        Start the thread or process
        """
        raise NotImplementedError()

    def _monitor_stop(self, on_stop: Callable, blocking: bool) -> None:
        def _stop(self):
            alive = self.alive()
            while self.alive():
                time.sleep(0.002)
            on_stop()
            self._status.state(State.off)

        if blocking:
            _stop(self)
        else:
            self._stop_thread = threading.Thread(target=_stop, args=(self,))
            self._stop_thread.start()

    @manage_error
    def stop(self, blocking: bool = False) -> None:
        """
        Request the thread / process to stop running.

        Args:
            blocking: If True, the method will block until
              the thread (or process) join.
        """
        raise NotImplementedError()

    @manage_error
    def stopped(self) -> bool:
        """
        Returns True if the current state if State.off,
        else False.
        """
        return self._status.get_state() == State.off

    @manage_error
    def on_exit(self):
        """
        This method can be called when the 'job' of the
        the Runner is completed.
        """
        raise NotImplementedError()

    @manage_error
    def alive(self) -> bool:
        """
        Returns True if the thread or process is still
        running
        """
        raise NotImplementedError()

    @manage_error
    def revive(self):
        """
        Restart the thread / process, if it died
        (does nothing if it is running)
        """
        raise NotImplementedError()

    def iterate(self):
        """
        Method to implement to have the Runner doing
        something useful.
        """
        raise NotImplementedError()

    def _frequency_iterate(self):
        self.iterate()
        self.wait()

    @manage_error
    def _run(self):
        raise NotImplementedError()


class ThreadRunner(Runner):
    """
    Calls the 'iterate' method in a thread.
    """

    def __init__(
        self,
        name: str,
        config_getter: ConfigGetter,
        frequency: float,
        interrupts: Iterable[Callable[[], bool]] = [],
        core_frequency: float = 0.005,
    ) -> None:
        super().__init__(name, config_getter, frequency, interrupts, core_frequency)
        self._thread: Optional[threading.Thread] = None
        self._running = False

    def message(self, msg: str, level: Optional[Level] = None) -> None:
        self._status.message(msg, level)

    def value(self, key: str, value: str, level: Optional[Level] = None) -> None:
        self._status.value(key, value, level=level)

    @manage_error
    def start(self):
        self._status.state(State.starting)
        self._thread = threading.Thread(target=self._run)
        self._running = True
        self._thread.start()
        self._status.state(State.running)

    def _on_stop(self) -> None:
        self._thread = None

    @manage_error
    def stop(self, blocking: bool = False) -> None:
        self._status.state(State.stopping)
        self._running = False
        self._monitor_stop(self._on_stop, blocking)

    @manage_error
    def alive(self) -> bool:
        if self._thread is None or not self._thread.is_alive():
            return False
        return True

    @manage_error
    def revive(self):
        if not self.alive():
            if self._thread is not None:
                del self._thread
            self.start()

    @manage_error
    def _run(self):
        self._running = True
        while self._running:
            self._frequency_iterate()
        self.on_exit()


class ProcessRunner(Runner):
    """
    Calls the 'iterate' method in a process.

    Compared to ThreadRunner, an instance of ProcessRunner
    has this limitation: it can access only shared memories
    that have been created prior to the call to its constructor.
    """

    def __init__(
        self,
        name: str,
        config_getter: ConfigGetter,
        frequency: float,
        interrupts: Iterable[Callable[[], bool]] = [],
        core_frequency: float = 0.005,
    ) -> None:
        super().__init__(name, config_getter, frequency, interrupts, core_frequency)
        self._running: MpValue = Value("i", False)
        self._process: Optional[Process] = None
        self._running = Value("i", False)

    @manage_error
    def start(self):
        self._status.state(State.starting)
        self._running.value = True
        self._process = Process(
            target=self.run, args=(SharedMemory.get_all(), self._running)
        )
        self._process.start()
        self._status.state(State.running)

    def _on_stop(self):
        self._process = None

    @manage_error
    def stop(self, blocking: bool = False) -> None:
        self._status.state(State.stopping)
        self._running.value = False
        self._monitor_stop(self._on_stop, blocking)

    @manage_error
    def alive(self) -> bool:
        if self._process is None:
            return False
        self._process.join(timeout=0)
        return self._process.is_alive()

    @manage_error
    def revive(self):
        if not self.alive():
            if self._process is not None:
                del self._process
            self.start()

    @manage_error
    def run(self, memories: dict[str, MultiPDict], running: MpValue) -> None:
        SharedMemory.set_all(memories)
        running.value = True  # type: ignore
        while running.value:  # type: ignore
            self._frequency_iterate()
        self.on_exit()
