import pytest
import time
from typing import Iterable, Callable, Generator, Type
from nightskyrunner.config_getter import FixedDictConfigGetter
from nightskyrunner.runner import Runner, ThreadRunner, ProcessRunner
from nightskyrunner.status import Status, State
from nightskyrunner.shared_memory import SharedMemory


class TestRunnerMixin:
    def __init__(self):
        SharedMemory.get("test")["value_out"] = 0
        SharedMemory.get("test")["value_in"] = 0

    def iterate(self):
        SharedMemory.get("test")["value_out"] = SharedMemory.get("test")["value_in"]


_name = "test_runner"
_config = FixedDictConfigGetter({})


def _interrupt() -> bool:
    try:
        value = SharedMemory.get("test")["interrupt"]
    except KeyError:
        return False
    return bool(value)


class ThreadTestRunner(TestRunnerMixin, ThreadRunner):
    def __init__(
        self,
        frequency: float,
        interrupts: Iterable[Callable[[], bool]] = [],
        core_frequency: float = 0.005,
    ) -> None:
        global _name
        global _config
        ThreadRunner.__init__(
            self, _name, _config, frequency, interrupts, core_frequency
        )
        TestRunnerMixin.__init__(self)


class ProcessTestRunner(TestRunnerMixin, ProcessRunner):
    def __init__(
        self,
        frequency,
        interrupts: Iterable[Callable[[], bool]] = [],
        core_frequency: float = 0.005,
    ) -> None:
        global _name
        global _config
        ProcessRunner.__init__(
            self, _name, _config, frequency, interrupts, core_frequency
        )
        TestRunnerMixin.__init__(self)


@pytest.fixture
def manage_shared_memory(request) -> Generator[None, None, None]:
    SharedMemory.get("test")
    yield
    SharedMemory.clear()


# @pytest.fixture(scope="function", params=[ThreadTestRunner, ProcessTestRunner])
@pytest.fixture(scope="function", params=[ThreadTestRunner])
def get_runner_class(request) -> Generator[Type[Runner], None, None]:
    runner_class = request.param
    yield runner_class


def test_basic_runner(manage_shared_memory, get_runner_class):
    global _name
    frequency = 100.0
    instance = get_runner_class(frequency)
    instance.start()
    for value in (2, 5, 9):
        SharedMemory.get("test")["value_in"] = value
        time.sleep(0.05)
        assert SharedMemory.get("test")["value_out"] == value
    status = Status.retrieve(_name)
    assert status.get()["state"] == State.running
    instance.stop()
    status = Status.retrieve(_name)
    assert status.get()["state"] == State.off


def test_interrupt(manage_shared_memory, get_runner_class):
    global _name
    frequency = 0.1
    instance = get_runner_class(frequency, interrupts=(_interrupt,))
    print("A")
    instance.start()
    print("B")
    time.sleep(0.01)
    instance.stop()
    print("C")
    time.sleep(0.01)
    assert Status.retrieve(_name).get()["state"] == State.stopping
    print("D")
    SharedMemory.get("test")["interrupt"] = True
    print("E")
    time.sleep(0.01)
    assert Status.retrieve(_name).get()["state"] == State.off
