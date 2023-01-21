"""
Tests for the nightskyrunner.runner module.
"""

import tempfile
import time
from pathlib import Path
from typing import Generator, Type, Union

import pytest
import tomli_w
from typing_extensions import TypedDict

from nightskyrunner.config_toml import DynamicTomlConfigGetter
from nightskyrunner.runner import (ProcessRunner, Runner, ThreadRunner,
                                   status_error)
from nightskyrunner.shared_memory import SharedMemory
from nightskyrunner.status import State, Status, wait_for_status
from nightskyrunner.wait_interrupts import RunnerWaitInterruptors


class _Error(Exception):
    # subclass of Exception
    ...


class TestRunnerDict(TypedDict):
    message: str


class _RunnerMixin:
    # this class will be used as a base class
    # of NotDecoratedRunner, ThreadTestRunner and
    # ProcessTestRunner (all defined in this file).
    # (to avoid re-implementing the iterate function)
    def __init__(self):
        SharedMemory.get("test")["value_out"] = 0
        SharedMemory.get("test")["value_in"] = 0
        SharedMemory.get("test")["error"] = False
        SharedMemory.get("test")["interrupt"] = False
        SharedMemory.get("test")["config_value"] = 0.0

    def iterate(self):
        # getting the config dictionary
        config = self.get_config()
        SharedMemory.get("test")["config_value"] = config["value"]
        # Another process can access this shared memory, and by checking the value
        # of SharedMemory.get("test")["value_out"], checking this iterate
        # function has been called with success
        SharedMemory.get("test")["value_out"] = SharedMemory.get("test")[
            "value_in"
        ]
        # Another process can set this shared memory, in which case this iterate
        # function raise an error. This allows to test an instance of Runner
        # status switch to "error" when its iterate function raises an error.
        if SharedMemory.get("test")["error"]:
            self._status.entries(TestRunnerDict(message="error"))
            raise _Error()
        else:
            self._status.entries(TestRunnerDict(message="running"))


def _write_config_toml(
    config_path: Path, frequency: float, value: float
) -> None:
    # updating the toml config file of the runner.
    config = {"frequency": frequency, "value": value}
    with open(config_path, "wb") as f:
        tomli_w.dump(config, f)


def _interrupt() -> bool:
    # if a test sets the shared memory "interrupt",
    # this function may return true.
    # This function can be used as a runner "RunnerWaitInterruptor",
    # i.e. a function that, when returning True,
    # commands the runner to stop sleeping.
    # Such an interruptor is useful for runners having a low frequency,
    # i.e. runners which sleep for a long time. For systems using such a
    # runner, keyboard interrupt to stop the manager will not work
    # as the runner will be sleeping in the background and not catching
    # the request to stop. An interrupt allows to break the sleep of the
    # runner, which can then propery stop upong keyboard interrupts.
    try:
        value = SharedMemory.get("test")["interrupt"]
    except KeyError:
        return False
    return bool(value)


class NotDecoratedRunner(_RunnerMixin, ThreadRunner):
    # all runner must be decorared with @status_error.
    # This runner is not decorated.
    # It allows to test a proper error is raised when
    # instantiating a non decorated runner.
    def __init__(
        self,
        frequency: float,
        config_toml_path: Path,
        interrupts: RunnerWaitInterruptors = [],
        core_frequency: float = 200.0,
        name: str = "test_thread_runner",
    ) -> None:
        _write_config_toml(config_toml_path, frequency, 1.0)
        config = DynamicTomlConfigGetter(config_toml_path)
        ThreadRunner.__init__(self, name, config, interrupts, core_frequency)
        _RunnerMixin.__init__(self)


@status_error
class ThreadTestRunner(_RunnerMixin, ThreadRunner):
    def __init__(
        self,
        frequency: float,
        config_toml_path: Path,
        interrupts: RunnerWaitInterruptors = [],
        core_frequency: float = 200.0,
        name: str = "test_thread_runner",
    ) -> None:
        self._path = config_toml_path
        _write_config_toml(config_toml_path, frequency, 1.0)
        config = DynamicTomlConfigGetter(config_toml_path)
        ThreadRunner.__init__(self, name, config, interrupts, core_frequency)
        _RunnerMixin.__init__(self)

    def get_config_path(self) -> Path:
        return self._path


@status_error
class ProcessTestRunner(_RunnerMixin, ProcessRunner):
    def __init__(
        self,
        frequency,
        config_toml_path: Path,
        interrupts: RunnerWaitInterruptors = [],
        core_frequency: float = 200.0,
        name: str = "test_process_runner",
    ) -> None:
        self._path = config_toml_path
        _write_config_toml(config_toml_path, frequency, 1.0)
        config = DynamicTomlConfigGetter(config_toml_path)
        ProcessRunner.__init__(self, name, config, interrupts, core_frequency)
        _RunnerMixin.__init__(self)

    def get_config_path(self) -> Path:
        return self._path


@pytest.fixture
def get_tmp_folder() -> Generator[Path, None, None]:
    tmp_dir_ = tempfile.TemporaryDirectory()
    tmp_dir = Path(tmp_dir_.name)
    yield tmp_dir
    tmp_dir_.cleanup()


@pytest.fixture
def get_toml_config_path(get_tmp_folder) -> Generator[Path, None, None]:
    tmp_dir = get_tmp_folder
    config_path = tmp_dir / "config.toml"
    yield config_path


@pytest.fixture
def manage_shared_memory(request) -> Generator[None, None, None]:
    # makes sure the shared memory is cleared between tests
    SharedMemory.get("test")
    yield
    SharedMemory.clear()


@pytest.fixture(scope="function", params=[ThreadTestRunner, ProcessTestRunner])
def get_runner_class(request) -> Generator[Type[Runner], None, None]:
    runner_class = request.param
    yield runner_class


@pytest.fixture
def instantiate_runner(
    request,
    get_toml_config_path,
    get_runner_class,
) -> Generator[Union[ThreadTestRunner, ProcessTestRunner], None, None]:
    # instantiate an instance of either ThreadTestRunner or ProcessTestRunner,
    # and stops it upon exit of the test.
    frequency, interrupts = request.param
    instance = get_runner_class(
        frequency, get_toml_config_path, interrupts=interrupts
    )
    instance.start()
    yield instance
    if not instance.stopped():
        instance.stop(blocking=True)


@pytest.mark.parametrize("instantiate_runner", [(100.0, [])], indirect=True)
def test_basic_runner(manage_shared_memory, instantiate_runner):
    """
    Testing basic runner's functionalities
    """
    instance = instantiate_runner
    instance.start()
    for value in (2, 5, 9):
        # the iterate method of the runner set the
        # value of 'value_out' to the value of 'value_in'
        SharedMemory.get("test")["value_in"] = value
        time_start = time.time()
        while SharedMemory.get("test")["value_out"] != value:
            time.sleep(0.01)
            if time.time() - time_start > 0.5:
                break
        # value out being equal to value in
        # means the iterate function of the runner
        # has been called with success.
        assert SharedMemory.get("test")["value_out"] == value
    status = Status.retrieve(instance.name)
    assert status.get()["state"] == State.running.name
    # checking the runner can stop when being asked to
    instance.stop(blocking=True)
    status = Status.retrieve(instance.name)
    assert status.get()["state"] == State.off.name


@pytest.mark.parametrize("instantiate_runner", [(100.0, [])], indirect=True)
def test_shared_memory(manage_shared_memory, instantiate_runner):
    """
    Test that existing shared memories are propery shared with
    runners, especially instances of ProcessRunner
    """
    instance = instantiate_runner
    assert wait_for_status(instance.name, State.running)
    SharedMemory.get("test")["value_in"] = 12
    time_start = time.time()
    while SharedMemory.get("test")["value_out"] != 12:
        time.sleep(0.01)
        if time.time() - time_start > 0.5:
            break
    assert SharedMemory.get("test")["value_out"] == 12
    instance.stop(blocking=True)


@pytest.mark.parametrize(
    "instantiate_runner", [(0.1, (_interrupt,))], indirect=True
)
def test_interrupt(manage_shared_memory, instantiate_runner):
    """
    Testing the interrupts are properly called
    """
    # low frequency setup on purpose
    #
    # see the parametrization of this test: the runner uses an interrupt function,
    # which when returning "True", should break the sleep of the runner
    # (sleep: between two calls of the iterate function of the runner)
    instance = instantiate_runner
    assert wait_for_status(instance.name, State.running)
    # requesting the runner to stop
    instance.stop()
    # because of the low frequency, the runner did not stop yet,
    # it is in the process of stopping (state==State.stopping)
    assert wait_for_status(instance.name, State.stopping)
    # checking it has not stopped yet
    assert not instance.stopped()
    # this triggers the interrupt to return True:
    #  - the instance is not stopped because of its low frequency (it is waiting)
    #  - setting the memory /test/interrupt to true should the waiting to break
    #    (see _interrupt function in this file which was passed as argument to the
    #     runner)
    #  - because the wait funtion breaks and stopping has been requested, the
    #    runner should then exit
    SharedMemory.get("test")["interrupt"] = True
    # checking all went as expected
    assert wait_for_status(instance.name, State.off)
    assert instance.stopped()


@pytest.mark.parametrize("instantiate_runner", [(100.0, [])], indirect=True)
def test_revive(manage_shared_memory, instantiate_runner):
    """
    Testing that a runner can be revived after
    experiencing an error
    """
    # This test triggers a pytest warning that
    # an error is not caught. This is correct, the
    # error is ignored, but instead the status of
    # the runner becomes "error".
    instance = instantiate_runner
    assert wait_for_status(instance.name, State.running)
    # triggers the iterate method to throw an error
    SharedMemory.get("test")["error"] = True
    SharedMemory.get("test")["interrupt"] = True
    assert wait_for_status(instance.name, State.error)
    # so that the iterate method will not throw an error
    # after the revive
    SharedMemory.get("test")["error"] = False
    SharedMemory.get("test")["interrupt"] = False
    if not instance.alive():
        instance.revive()
    assert wait_for_status(instance.name, State.running)


@pytest.mark.parametrize("instantiate_runner", [(100.0, [])], indirect=True)
def test_message(manage_shared_memory, instantiate_runner):
    """
    Testing the message method of runner
    """
    instance = instantiate_runner
    assert wait_for_status(instance.name, State.running)
    message = Status.retrieve(instance.name).get()["entries"]["message"]
    assert message == "running"
    SharedMemory.get("test")["error"] = True
    assert wait_for_status(instance.name, State.error)
    message = Status.retrieve(instance.name).get()["entries"]["message"]
    assert message == "error"
    SharedMemory.get("test")["error"] = False
    if not instance.alive():
        instance.revive()
    assert wait_for_status(instance.name, State.running)
    message = Status.retrieve(instance.name).get()["entries"]["message"]
    assert message == "running"


@pytest.mark.parametrize("instantiate_runner", [(100.0, [])], indirect=True)
def test_running_for(manage_shared_memory, instantiate_runner):
    """
    Testing the status field "running_for" does not become None
    after a runner is revived.
    """
    instance = instantiate_runner
    assert wait_for_status(instance.name, State.running)
    time.sleep(0.2)
    running_for = Status.retrieve(instance.name).get()["running_for"]
    assert running_for is not None
    assert running_for
    assert float(running_for) > 0.2
    SharedMemory.get("test")["error"] = True
    assert wait_for_status(instance.name, State.error)
    SharedMemory.get("test")["error"] = False
    if not instance.alive():
        instance.revive()
    assert wait_for_status(instance.name, State.running)
    time.sleep(0.2)
    running_for = Status.retrieve(instance.name).get()["running_for"]
    assert running_for is not None
    assert float(running_for) > 0.2
    assert float(running_for) < 0.4


@pytest.mark.parametrize("instantiate_runner", [(100.0, [])], indirect=True)
def test_config_update(
    manage_shared_memory, instantiate_runner, get_tmp_folder
):
    """
    Testing the status field "running_for" does not become None
    after a runner is revived.
    """
    instance = instantiate_runner
    assert wait_for_status(instance.name, State.running)
    assert SharedMemory.get("test")["config_value"] == 1.0
    updated_config_path = get_tmp_folder / "updated.toml"
    _write_config_toml(updated_config_path, 100.0, 2.0)
    SharedMemory.get(instance.name)["path"] = updated_config_path
    time_start = time.time()
    while SharedMemory.get("test")["config_value"] != 2.0:
        time.sleep(0.01)
        if time.time() - time_start > 0.5:
            break
    assert SharedMemory.get("test")["config_value"] == 2.0


def test_status_error_enforced(get_toml_config_path):
    """
    Check that concrete subclasses of Runner
    that are not decorated with "status_error"
    throw a TypeError when being constructed.
    """
    _write_config_toml(get_toml_config_path, 1.0, 1.0)
    with pytest.raises(TypeError):
        NotDecoratedRunner(1.0, get_toml_config_path)
