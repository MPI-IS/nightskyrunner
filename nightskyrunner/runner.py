from functools import wraps
from multiprocessing import Process, Value
from . import status
from . import configcheck
from .config_getter import ConfigGetter


def manage_error(method):
    @wraps(method)
    def _impl(self, *args, **kwargs):
        try:
            method(self, *args, **kwargs)
        except Exception as e:
            self.state(State.error, f"{type(e)}: {e}")

    return _impl


class Runner(status.Status):
    def __init__(self, name: str, config_getter: ConfigGetter) -> None:
        super().__init__(name)
        self._config_getter = config_getter

    @manage_error
    def start(self):
        raise NotImplementedError()

    @manage_error
    def stop(self):
        raise NotImplementedError()

    @manage_error
    def on_exit(self):
        raise NotImplementedError()

    @manage_error
    def revive(self):
        raise NotImplementedError()

    @manage_error
    def iterate(self):
        raise NotImplementedError()

    @manage_error
    def run(self):
        raise NotImplementedError()


class ThreadRunner(Runner):
    def __init__(self, name: str, config_getter: ConfigGetter) -> None:
        super().__init__(name, config_getter)
        self._thread: typing.Optional[threading.Thread] = None
        self._running = False

    @manage_error
    def start(self):
        self.state(State.starting)
        self._thread = threading.Thread(target=self.run)
        self._running = True
        self._thread.start()
        self.state(State.running)

    @manage_error
    def stop(self):
        self._running = False
        if self._thread is not None:
            self._thread.join()
        self._thread = None
        self.state(State.off)

    @manage_error
    def revive(self):
        if self._thread is None or not self._thread.is_alive():
            if self._thread is not None:
                del self._thread
            self.start()

    @manage_error
    def run(self):
        self._running = True
        while self._running:
            self.iterate()
        self.on_exit()


class ProcessRunner(Runner):
    def __init__(self, name: str, config_getter: ConfigGetter) -> None:
        super().__init__(name, config_getter)
        self._running = Value("i", False)
        self._process: typing.Optional[Process] = None
        self._running = Value("i", False)
        
    @manage_error
    def start(self):
        self.state(State.starting)
        self._running.value = True
        self._process = Process(
            target=self.run,
            args=(SharedMemory.get_all(), self._running)
        )
        self._process.start()
        self.state(State.running)

    @manage_error
    def stop(self):
        self._running.value = False
        if self._process is not None:
            self._process.join()
        self._process = None
        self.state(State.off)

    def _alive(self)->bool:
        if self._process is None:
            return False
        self._process.join(timeout=0)
        return self._process.is_alive():
        
    @manage_error
    def revive(self):
        if not self._alive:
            if self._process is not None:
                del self._process
            self.start()

    @manage_error
    def run(
            self,
            memories: dict[str, MultiPDict],
            running: Value
    )->None:
        SharedMemory.set_all(memories)
        running.value = True
        while running.value:
            self.iterate()
        self.on_exit()
