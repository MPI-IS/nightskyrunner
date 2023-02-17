import pytest
from typing import Iterable, Callable, Generator, Type
from nightskyrunner.config_getter import FixedDictConfigGetter
from nightskyrunner.runner import Runner, ThreadRunner, ProcessRunner
from nightskyrunner.status import Status, State
from nightskyrunner.shared_memory import SharedMemory

class TestRunnerMixin:
    def __init__(self):
        self.count = 0
        SharedMemory.get("test")["value_out"] = 0
        SharedMemory.get("test")["value_in"] = 0

    def iterate(self):
        self.count += 1
        SharedMemory.get("test")["value_out"] = SharedMemory.get("test")["value_in"]


_name = "test_runner"
_config = FixedDictConfigGetter({})
_frequency = 0.01


def _interrupt() -> bool:
    try:
        value = SharedMemory.get("test")["interrupt"]
    except KeyError:
        return False
    return bool(value)


class ThreadTestRunner(ThreadRunner, TestRunnerMixin):
    def __init__(
        self,
        interrupts: Iterable[Callable[[], bool]] = [],
        core_frequency: float = 0.005,
    ) -> None:
        global _name
        global _config
        global _frequency
        ThreadRunner.__init__(
            self, _name, _config, _frequency,
            interrupts, core_frequency
        )
        TestRunnerMixin.__init__(self)


class ProcessTestRunner(ProcessRunner, TestRunnerMixin):
    def __init__(
        self,
        interrupts: Iterable[Callable[[], bool]] = [],
        core_frequency: float = 0.005,
    ) -> None:
        global _name
        global _config
        global _frequency
        ProcessRunner.__init__(
            self, _name, _config, _frequency,
            interrupts, core_frequency
        )
        TestRunnerMixin.__init__(self)


@pytest.fixture
def manage_shared_memory(request) -> Generator[None, None, None]:
    SharedMemory.get("test")
    yield
    SharedMemory.clear()


@pytest.fixture(scope="function", params=[ThreadTestRunner, ProcessTestRunner])
def get_runner_class(request) -> Generator[Type[Runner], None, None]:
    runner_class = request.param
    yield runner_class


def test_basic_runner(manage_shared_memory, get_runner_class):
    global _name
    instance = get_runner_class()
    instance.start()
    SharedMemory.get("test")["value_in"] = 5
    time.sleep(0.1)
    status = Status.retrieve(_name)
    assert status.get()["state"] == State.running
    instance.stop()
    status = Status.retrieve(_name)
    assert status.get()["state"] == State.off
    assert instance.count > 1
    assert SharedMemory.get("test")["value_out"] == 5
