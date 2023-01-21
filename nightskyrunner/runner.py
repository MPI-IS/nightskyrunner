from typing import Dict

"""
Module defining the class Runner (and subclasses ThreadRunner and ProcessRunner).
A Runner manages a thread (or a process) which calls at its given frequency a custom "iterate"
method ('custom': developpers create subclasses of Runner implementing this method).
"""

import inspect
import logging
import threading
import time
import traceback
from contextlib import contextmanager
from multiprocessing import Process, Value
from typing import Any, Callable, Iterable, Optional

from .config import Config
from .config_error import ConfigError
from .config_getter import ConfigGetter
from .shared_memory import DictProxy, MpValue, SharedMemory
from .status import Level, State, Status
from .wait_interrupts import RunnerWaitInterruptors


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
        self._keyboard_interrupted: bool = False
        self._core_frequency = core_frequency
        self._lock = threading.Lock()

    def set_frequency(self, frequency: float) -> None:
        with self._lock:
            self._period = 1.0 / frequency

    def wait(self):
        """
        Wait the time required to enforce the desired frequency,
        except if any of the 'interrupt' callable returns True
        """
        if self._previous is None:
            with self._lock:
                self._previous = time.time()
        while True:
            try:
                with self._lock:
                    if time.time() - self._previous > self._period:
                        break
                for interrupt in self._interrupts:
                    if interrupt():
                        self._previous = time.time()
                        return
                time.sleep(1.0 / self._core_frequency)
            except KeyboardInterrupt:
                self._keyboard_interrupted = True
                break
        self._previous = time.time()


def _clearer_error_message(e: Exception) -> str:
    tb = traceback.extract_tb(e.__traceback__)
    file_name = tb[-1].filename
    line_number = tb[-1].lineno
    error_msg = f"{file_name} ({line_number}), {e.__class__.__name__}: {e}"
    return error_msg


def _status_error(class_: type, name: str, method: Callable):
    def catching_error(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except KeyboardInterrupt:
            self.log(Level.info, "keyboard interrupt")
        except Exception as e:
            error_msg = _clearer_error_message(e)
            self.log(Level.error, error_msg)
            self._status.state(State.error, error_msg)
            raise e

    setattr(class_, name, catching_error)


def status_error(class_: type) -> type:
    """
    Class decorator which ensure any exception raised by a public
    method of the class which is not 'iterate' results in the status of
    the instance to be switched to 'error'.

    (error raised by 'iterate' are handled separately).

    Concrete subclasses of Runner must be decorated by this decorator.
    Subclasses of Runner that are not decorared raise a TypeError
    when being constructed.
    """
    methods = inspect.getmembers(class_, predicate=inspect.isfunction)
    for name, method in methods:
        if not name[0] == "_" and not name == "iterate":
            _status_error(class_, name, method)
    setattr(class_, "_status_error", True)
    return class_


class Runner(_Sleeper):
    """
    A Runner manages a thread (ThreadRunner virtual subclass) or a process
    (ProcessRunner virtual subclass) which calls at its given frequency
    an 'iterate' method (to be implemented by concrete subclasses).

    An instance of Runner encapsulates an instance of Status, which
    it uses to inform the external world of its status. The instance
    of status can be retrieved by using the Runner's name:

    ```python
    # name is the string that has been passed as argument to
    # the runner's constructor.
    status = Status.retrieve(name)
    ```

    Concrete subclasses of Runner must be decorated with "status_error":
    this ensure that the status of an instance of Runner is switched to
    "error" if an exception is thrown by any of the public instance's
    method. Subclasses that are not decorated raise a TypeError when
    being constructed.

    Args:
      name: arbitrary name of the runner. Can be used to retrieve's the
        runners' status
      config_getter: instance in charge to return the runner's configuration
        dictionary (can be used in the 'iterate' method)
      core_frequency: frequency at which the runner will call the 'iterate' method
      interrupts: if any interrupt returns True (and for as long the interrupt
        returns True), there will be no wait between calls to 'iterate'. If
        an interrupt returns True during the wait, the wait is interrupted.
        Expected usage: If the frequency is low, an instance of runner may take a
        long time to exit after a call to the 'stop' method. An interrupt allows
        for shortening this time
      core_frequency: frequency at which interrupts will be called.

    Raises:
      TypeError: if the class is not decorated with 'status_error'
    """

    def __init__(
        self,
        name: str,
        config_getter: ConfigGetter,
        interrupts: RunnerWaitInterruptors = [],
        core_frequency: float = 200.0,
        stop_priority: int = 0,
    ) -> None:
        if not hasattr(self.__class__, "_status_error"):
            raise TypeError(
                f"{self.__class__.__name__}: "
                "concrete subclasses of Runner must be decorated with 'status_error'"
            )
        self._status = Status(name, self.__class__.__name__)
        self._logger = logging.getLogger(name)
        self._name = name
        self._stop_priority = stop_priority
        self._config_getter = config_getter
        self._initialize()
        frequency = self._read_frequency()
        _Sleeper.__init__(self, frequency, interrupts, core_frequency)

    def stop_priority(self) -> int:
        return self._stop_priority

    def _read_frequency(self) -> float:
        config = self._config_getter.get()
        if "frequency" not in config.keys():
            error = str(
                "All runners requires a 'frequency' configuration field "
                f"(missing for the runner '{self._name}')"
            )
            raise ConfigError(error)
        try:
            frequency = float(config["frequency"])  # type: ignore
        except ValueError:
            raise ConfigError(
                f"Unsuitable frequency configuration value for {self._name}: "
                f"{config['frequency']} (a float is required)"
            )
        return frequency

    def _shared_memory_config_update(self) -> None:
        data = SharedMemory.get(self._name)
        config = self._config_getter.get(vars=False)
        data["config"] = repr(config)
        self._config_getter.update(data)

    def _initialize(self) -> None:
        # to be called before the runner is started,
        # to ensure the shared memory is created
        # (otherwise will not be accessible to the
        # instances of ProcessRunner)
        self._shared_memory_config_update()

    def log(self, level: Level, message: Any) -> None:
        logfunc = getattr(self._logger, str(level.name))
        logfunc(f"\t{message}")

    @property
    def name(self) -> str:
        """
        the name of the Runner (as passed as argument
        to the constructor)
        """
        return self._status.name

    def get_config(self) -> Config:
        c = self._config_getter.get()
        return c

    def start(self):
        """
        Start the thread or process
        """
        raise NotImplementedError()

    def _monitor_stop(self, on_stop: Callable, blocking: bool) -> None:
        def _stop(self):
            self.log(Level.info, "stopping")
            while self.alive():
                time.sleep(0.002)
            on_stop()
            self._status.state(State.off)
            self.log(Level.info, "stopped")

        if blocking:
            _stop(self)
        else:
            self._stop_thread = threading.Thread(target=_stop, args=(self,))
            self._stop_thread.start()

    def stop(self, blocking: bool = False) -> None:
        """
        Request the thread / process to stop running.

        Args:
          blocking: If True, the method will block until
            the thread (or process) join.
        """
        raise NotImplementedError()

    def stopped(self) -> bool:
        """
        Returns True if the current state if State.off,
        else False.
        """
        return self._status.get_state() == State.off

    def on_exit(self) -> None:
        """
        This method can be called when the 'job' of the
        the Runner is completed.
        """
        ...

    def alive(self) -> bool:
        """
        Returns True if the thread or process is still
        running
        """
        raise NotImplementedError()

    def revive(self) -> None:
        """
        Restart the thread / process, if it died
        (does nothing if it is running)
        """
        raise NotImplementedError()

    def iterate(self) -> None:
        """
        Method to implement to have the Runner doing
        something useful.
        """
        raise NotImplementedError()

    def _frequency_iterate_error(
        self, e: Exception, error_state: bool = True
    ) -> None:
        error_msg = _clearer_error_message(e)
        self.log(Level.error, error_msg)
        if error_state:
            self._status.state(State.error, error_msg)
        try:
            self.on_exit()
        except Exception:
            pass

    def _frequency_iterate(self) -> None:
        if self._keyboard_interrupted:
            return
        try:
            self._shared_memory_config_update()
        except Exception as e:
            self._frequency_iterate_error(e, False)
        try:
            frequency = self._read_frequency()
            self.set_frequency(frequency)
            self._status.activity("iterating")
            self.iterate()
        except Exception as e:
            self._frequency_iterate_error(e, True)
        else:
            self._status.state(State.running)
        self._status.activity("sleep")
        try:
            self.wait()
        except Exception as e:
            self._frequency_iterate_error(e, True)

    def _run(self) -> None:
        raise NotImplementedError()

    @classmethod
    def default_config(cls) -> Config:
        raise NotImplementedError()


class ThreadRunner(Runner):
    """
    Calls the 'iterate' method in a thread.
    """

    def __init__(
        self,
        name: str,
        config_getter: ConfigGetter,
        interrupts: RunnerWaitInterruptors = [],
        core_frequency: float = 1.0 / 0.005,
        stop_priority: int = 0,
    ) -> None:
        super().__init__(
            name,
            config_getter,
            interrupts=interrupts,
            core_frequency=core_frequency,
            stop_priority=stop_priority,
        )
        self._thread: Optional[threading.Thread] = None
        self._running = False

    def start(self):
        if self._status.get_state() != State.error:
            self._status.state(State.starting)
        self._thread = threading.Thread(target=self._run)
        self._running = True
        self._thread.start()

    def _on_stop(self) -> None:
        self._thread = None

    def stop(self, blocking: bool = False) -> None:
        self._status.state(State.stopping)
        self._running = False
        self._monitor_stop(self._on_stop, blocking)

    def alive(self) -> bool:
        if self._thread is None or not self._thread.is_alive():
            return False
        return True

    def revive(self):
        while self.alive():
            time.sleep(1.0 / self._core_frequency)
        if self._thread is not None:
            del self._thread
            self._thread = None
        self.start()

    def _run(self):
        self._running = True
        while self._running:
            try:
                self._frequency_iterate()
            except Exception:
                break
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
        interrupts: RunnerWaitInterruptors = [],
        core_frequency: float = 1.0 / 0.005,
        stop_priority: int = 0,
    ) -> None:
        super().__init__(
            name,
            config_getter,
            interrupts,
            core_frequency,
            stop_priority,
        )
        self._running: MpValue = Value("i", False)
        self._process: Optional[Process] = None
        self._running = Value("i", False)
        self._starting = False

    @contextmanager
    def _manage_starting(self):
        self._starting = True
        yield None
        self._starting = False

    def start(self):
        self._starting = True
        self._running.value = True
        with self._manage_starting():
            if self._status.state != State.error:
                self._status.state(State.starting)
            self._process = Process(
                target=self.run,
                args=(SharedMemory.get_all(), self._running),
            )
            self._process.start()

    def _on_stop(self):
        self._process = None

    def stop(self, blocking: bool = False) -> None:
        while self._starting:
            time.sleep(1.0 / self._core_frequency)
        self._status.state(State.stopping)
        self._running.value = False  # type: ignore
        self._monitor_stop(self._on_stop, blocking)

    def alive(self) -> bool:
        if self._process is None:
            return False
        self._process.join(timeout=0.1)
        return self._process.is_alive()

    def revive(self):
        self._starting = True
        self._running.value = True
        with self._manage_starting():
            while self.alive():
                time.sleep(1.0 / self._core_frequency)
            if self._process is not None:
                del self._process
                self._process = None
            self.start()

    def run(self, memories: Dict[str, DictProxy], running: MpValue) -> None:
        SharedMemory.set_all(memories)
        # note: running.value set to True by start and revive
        while running.value:  # type: ignore
            try:
                self._frequency_iterate()
            except Exception:
                break
        self.on_exit()
