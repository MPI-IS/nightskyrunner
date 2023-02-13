from functools import wraps
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
        self._running = multiprocessing.Value("i", False)
        self._process: typing.Optional[multiprocessing.Process] = None
        self._sm_module = shared_memory

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


        
