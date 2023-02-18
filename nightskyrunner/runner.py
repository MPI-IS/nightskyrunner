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
    @wraps(method)
    def _impl(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except Exception as e:
            self._status.state(State.error, f"{type(e)}: {e}")

    return _impl


class _Sleeper:
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
        if self._previous is None:
            self._previous = time.time() - self._period
        while time.time() - self._previous < self._period:
            for interrupt in self._interrupts:
                if interrupt():
                    self._previous = time.time()
                    return
            time.sleep(self._core_frequency)
        self._previous = time.time()


# TODO: use class decorator to decorate all method with "manage_error"
class Runner(_Sleeper):
    def __init__(
        self,
        name: str,
        config_getter: ConfigGetter,
        frequency: float,
        interrupts: Iterable[Callable[[], bool]] = [],
        core_frequency: float = 0.005,
    ) -> None:
        _Sleeper.__init__(self, frequency, interrupts, core_frequency)
        self._status = Status(name)
        self._config_getter = config_getter

    @property
    def name(self)->str:
        return self._status.name
        
    @manage_error
    def start(self):
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
    def stop(self, blocking: bool=False)->None:
        raise NotImplementedError()

    @manage_error
    def stopped(self) -> bool:
        return self._status.get_state() == State.off

    @manage_error
    def on_exit(self):
        raise NotImplementedError()

    @manage_error
    def alive(self) -> bool:
        raise NotImplementedError()

    @manage_error
    def revive(self):
        raise NotImplementedError()

    def iterate(self):
        raise NotImplementedError()

    def frequency_iterate(self):
        self.iterate()
        self.wait()

    @manage_error
    def run(self):
        raise NotImplementedError()


class ThreadRunner(Runner):
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
        self._thread = threading.Thread(target=self.run)
        self._running = True
        self._thread.start()
        self._status.state(State.running)

    def _on_stop(self) -> None:
        self._thread = None

    @manage_error
    def stop(self, blocking: bool =False)->None:
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
    def run(self):
        self._running = True
        while self._running:
            self.frequency_iterate()
        self.on_exit()


class ProcessRunner(Runner):
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
    def stop(self, blocking: bool=False)->None:
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
            self.frequency_iterate()
        self.on_exit()
