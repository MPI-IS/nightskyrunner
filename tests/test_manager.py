"""
Tests for Manager and DynamicTomlManagerConfigGetter.
"""

import tempfile
import time
from pathlib import Path
from typing import Generator, Iterable, Union

import pytest
import tomli_w

from nightskyrunner.config_toml import (
    DynamicTomlManagerConfigGetter,
    TomlManagerConfigGetter,
)
from nightskyrunner.manager import Manager
from nightskyrunner.shared_memory import clean_shared_memory
from nightskyrunner.status import State, wait_for_status


@pytest.fixture
def get_tmp(request, scope="function") -> Generator[Path, None, None]:
    """
    Returns a temporary directory path
    """
    tmp_dir_ = tempfile.TemporaryDirectory()
    tmp_dir = Path(tmp_dir_.name)
    yield tmp_dir
    tmp_dir_.cleanup


def _set_toml_config_value(
    directory: Path, runner_name: str, value: Union[int, str]
) -> Path:
    # Write a configuration toml file for the runner.
    # The keys of the configuration file matches the configuration
    # keys required by the tests.TestThreadRunner and tests.TestProcessRunner
    # used in these tests.
    # The code of tests.TestThreadRunner and tests.TestProcessRunner assumes
    # that the value of "field" will be an int. If value is a string,
    # the runner is expected to switch to error status.
    path = directory / f"{runner_name}.toml"
    d = {"frequency": 10.0, "field": value, "goodbye": "{{ goodbye }}"}
    with open(path, "wb") as f:
        tomli_w.dump(d, f)
    return path


def _write_manager_toml(
    runner_class_name: str, runners: Iterable[str], directory: Path
) -> Path:
    # Write a manager configuration toml file, suitable for spawning
    # instances of tests.TestThreadRunner and tests.TestProcessRunner
    content = []
    for runner_name in runners:
        content.append(
            f"""
            [{runner_name}]
            class_runner = "nightskyrunner.tests.{runner_class_name}"
            class_config_getter = "nightskyrunner.config_toml.DynamicTomlConfigGetter"
            args = ["{_set_toml_config_value(directory, runner_name, 0)}"]
            [{runner_name}.kwargs]
            "vars" =  "{directory}/vars.toml"
            """
        )
    path = directory / "manager.toml"
    with open(path, "w+") as f:
        f.write("\n".join(content))
    vars_path = directory / "vars.toml"
    with open(vars_path, "w+") as f:
        f.write('goodbye = "goodbye from test"')
    return path


def test_fixed_toml(get_tmp):
    """
    Test that TomlManagerConfigGetter can instantiate
    correctly instances of RunnerFactory
    """
    tmp_dir = get_tmp
    runner_names = ("runner1", "runner2")
    for runner_class_name in ("TestThreadRunner", "TestProcessRunner"):
        manager_path = _write_manager_toml(
            runner_class_name, runner_names, tmp_dir
        )
        static_toml_file = TomlManagerConfigGetter(manager_path)
        runner_factories = static_toml_file.get()
        assert len(runner_factories) == 2
        assert set([rf.name for rf in runner_factories]) == set(runner_names)
        runners = [rf.instantiate([]) for rf in runner_factories]
        assert set([r.name for r in runners]) == set(runner_names)


def test_manager_basics(get_tmp):
    """
    Test the basic functionality of a Manager, i.e.
    spawns correctly runners which are dynamically
    configurable
    """
    tmp_dir = get_tmp
    runner_names = ("runner1", "runner2")
    for runner_class_name in (
        "TestThreadRunner",
        "TestProcessRunner",
    ):
        # writing the manager toml configuration file (requesting the manager
        # to spawn runner of class TestThreadRunner and TestProcessRunner.
        # Source code of these class is in nightskyrunner.tests.py.
        manager_path = _write_manager_toml(
            runner_class_name, runner_names, tmp_dir
        )

        # a DynamicTomlManagerConfigGetter reads continuously the configuration
        # file. I.e. manager_config_getter will allow the manager to detect
        # changes in the content of the file at the path manager_path
        manager_config_getter = DynamicTomlManagerConfigGetter(manager_path)

        with Manager(
            manager_config_getter, core_frequency=50.0, keep_shared_memory=True
        ) as manager:
            # the context manager will have the manager reading its config
            # file and spawning the corresponding instances of runner
            assert wait_for_status("runner1", State.running)
            assert wait_for_status("runner2", State.running)
            assert manager.alive()

            # in this new list of runners, runner2 is removed and
            # runner3 is added. Consequently, runner2 should turn off and
            # runner3 should turn on. This works because manager_config_getter
            # is an instance of DynamicTomlManagerConfigGetter (dynamic being
            # the keyword here)
            runner_names = ("runner1", "runner3")
            _write_manager_toml(runner_class_name, runner_names, tmp_dir)
            assert wait_for_status("runner1", State.running)
            assert wait_for_status("runner2", State.off)
            assert wait_for_status("runner3", State.running)
            assert manager.alive()

            # We change the configuration of runner1. runner1 expects
            # an int value, but instead we give a string. Consequently
            # runner1 state should switch to "error".
            # note: this will result in a pytest warning
            #   that an error is not caught. This is correct, the
            #   error is ignored, but instead the status of runner1
            #   becomes 'error'
            _set_toml_config_value(
                tmp_dir, "runner1", "should be an int but is a string"
            )
            assert wait_for_status("runner1", State.error)
            assert wait_for_status("runner2", State.off)
            assert wait_for_status("runner3", State.running)
            assert manager.alive()

            # We change back the configuration runner1 to something
            # correct (i.e. an int). The status of runner1 should
            # come back to the state "running".
            _set_toml_config_value(tmp_dir, "runner1", 0)
            assert wait_for_status("runner1", State.running)
            assert wait_for_status("runner2", State.off)
            assert wait_for_status("runner3", State.running)
            assert manager.alive()

            # Adding runner2 again, which should turn on.
            runner_names = ("runner1", "runner2", "runner3")
            _write_manager_toml(runner_class_name, runner_names, tmp_dir)
            assert wait_for_status("runner1", State.running)
            assert wait_for_status("runner2", State.running)
            assert wait_for_status("runner3", State.running)
            assert manager.alive()

        time.sleep(0.1)

        with clean_shared_memory():
            # The runner should have turned off when we exited
            # the context manager.
            # (we can still access status in the shared memory
            # because keep_shared_memory is True)
            assert wait_for_status("runner1", State.off)
            assert wait_for_status("runner2", State.off)
            assert wait_for_status("runner3", State.off)
