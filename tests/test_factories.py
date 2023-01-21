"""
Tests for the nightskyrunner.config_getter module
"""

import tempfile
from pathlib import Path
from typing import Any, Dict, Generator

import pytest
import tomli_w

from nightskyrunner.config import Config
from nightskyrunner.config_getter import ConfigGetter, FixedDict
from nightskyrunner.config_toml import (DynamicTomlConfigGetter,
                                        TomlRunnerFactory, _toml_config_getter)
from nightskyrunner.dotted import DottedPath, get_from_dotted
from nightskyrunner.factories import BasicRunnerFactory, _build_config_getter
from nightskyrunner.runner import ThreadRunner, status_error
from nightskyrunner.shared_memory import SharedMemory
from nightskyrunner.tests import TestProcessRunner, TestThreadRunner
from nightskyrunner.wait_interrupts import RunnerWaitInterruptors


@pytest.fixture
def get_tmp(request, scope="function") -> Generator[Path, None, None]:
    """
    Returns a temporary directory path
    """
    tmp_dir_ = tempfile.TemporaryDirectory()
    tmp_dir = Path(tmp_dir_.name)
    yield tmp_dir
    tmp_dir_.cleanup


def test_method_dotted() -> None:
    """
    Test if the get_from_dotted function
    allows to get pointer to function
    """

    # here we will try to get the python
    # method get_from_dotted given its dotted
    # path.
    path = "nightskyrunner.dotted.get_from_dotted"
    method = get_from_dotted(path)
    assert method.__name__ == "get_from_dotted"

    prefixes = (
        "nightskyrunner.whatever1",
        "nightskyrunner.factories",
        "nightskyrunner.whatever2",
    )
    method = get_from_dotted("get_from_dotted", prefixes)
    assert method.__name__ == "get_from_dotted"


def test_class_dotted() -> None:
    """
    Test if the get_from_dotted function
    allows to get pointer to class
    """

    path = "nightskyrunner.config_error.ConfigError"
    class_ = get_from_dotted(path)
    assert class_.__name__ == "ConfigError"

    prefixes = (
        "nightskyrunner.whatever1",
        "nightskyrunner.config_error",
        "nightskyrunner.whatever2",
    )
    class_ = get_from_dotted("ConfigError", prefixes)
    assert class_.__name__ == "ConfigError"


def test_ext_lib_dotted() -> None:
    """
    Test if the get_from_dotted function
    allows to extract class from an "external"
    (e.g. pip installed) package
    """
    path = "pathlib.Path"
    class_ = get_from_dotted(path)
    assert class_.__name__ == "Path"


def test_build_config_getter() -> None:
    """
    Test for the build_config_getter function.
    """

    # FixedDict is a subclass of ConfigGetter.
    # The build_config_getter function should be able
    # to instantiate FixedDict based on a dotter path
    # and arguments (supported by FixedDict constructor)

    class_path = DottedPath("nightskyrunner.config_getter.FixedDict")
    fixed_config = {"field1": 0, "field2": 12}
    args = (fixed_config,)
    kwargs: Dict[str, Any] = {}

    # instantiating FixedDict and checking the arguments were
    # passed correctly
    config_getter = _build_config_getter(class_path, args, kwargs)
    assert isinstance(config_getter, FixedDict)
    config = config_getter.get()
    for k, v in config.items():
        assert fixed_config[k] == v
    for k, v in fixed_config.items():
        assert config[k] == v

    # instantiating FixedDict and checking the keyword arguments were
    # passed correctly
    kwargs = {"override": {"field2": -6}}
    config_getter = _build_config_getter(class_path, args, kwargs)
    assert isinstance(config_getter, FixedDict)
    config = config_getter.get()
    assert config["field1"] == 0
    assert config["field2"] == -6


def test_toml_config_getter(get_tmp) -> None:
    """
    Test for the (private) _toml_config_getter
    function. The _toml_config_getter is not used
    but this test is useful as a proxy to the test
    of the dict_config_getter method.
    """
    tmp_dir = get_tmp

    config_path = tmp_dir / "config.toml"
    config = {
        "field1": 0,
        "field2": 12,
        "field3": {"field31": 100, "field32": -6},
    }
    with open(config_path, "wb") as f:
        tomli_w.dump(config, f)

    main_path = tmp_dir / "main.toml"

    toml_content = {
        "class": "nightskyrunner.config_toml.DynamicTomlConfigGetter",
        "args": [f"{config_path}"],
        "kwargs": {},
    }
    with open(main_path, "wb") as f:
        tomli_w.dump(toml_content, f)

    # create an instance of DynamicTomlConfigGetter
    # based on the content of toml_content
    config_getter = _toml_config_getter(main_path)
    assert isinstance(config_getter, DynamicTomlConfigGetter)

    # The config getter returns an instance of Config,
    # the content of which corresponds to the one of the file config.toml
    # created at the beginning of this test.
    get_config = config_getter.get()
    assert get_config["field1"] == 0
    assert get_config["field2"] == 12
    assert get_config["field3"]["field31"] == 100
    assert get_config["field3"]["field32"] == -6


def test_runner_factory(get_tmp) -> None:
    """
    Tests for TomlRunnerFactory
    """

    @status_error
    class ThreadTestRunner(ThreadRunner):
        def __init__(
            self,
            name: str,
            config_getter: ConfigGetter,
            interrupts: RunnerWaitInterruptors = [],
            core_frequency: float = 200.0,
        ) -> None:
            ThreadRunner.__init__(self, name, config_getter, interrupts, core_frequency)

        def iterate(self):
            d = SharedMemory.get("testf")
            config = self.get_config()
            d["c1"] = config["c1"]
            d["c2"] = config["c2"]

    tmp_dir = get_tmp

    # creating a toml configuration file suitable for
    # an instance of ThreadTestRunner
    config = {"frequency": 10.0, "c1": +2, "c2": -1}
    config_path = tmp_dir / "config.toml"
    with open(config_path, "wb+") as f:
        tomli_w.dump(config, f)

    # A TomlRunnerFactory that will allow instantiation of ThreadTestRunner
    # configured by the toml file config_path. The configuration will be dynamic
    # (because based on the subclass DynamicTomlConfigGetter of ConfigGetter).
    name = "runner_test"  # name of the instance of the runner
    runner = ThreadTestRunner  # class of the runner
    # which subclass of ConfigGetter will the instance of ThreadTestRunner
    # to get its configuration at runtime
    config_getter = DottedPath("nightskyrunner.config_toml.DynamicTomlConfigGetter")
    # DynamicTomlConfigGetter gets the path to the toml config file as argument
    args = [
        str(config_path),
    ]
    kwargs: Dict[str, Any] = {}
    # the runner factory will be able to create instances of ThreadTestRunner
    runner_factory = TomlRunnerFactory(
        name,
        runner,
        config_getter,
        args=args,
        kwargs=kwargs,
    )

    # instance is an instance of ThreadTestRunner
    instance = runner_factory.instantiate()
    instance.iterate()
    # when iterating, "instance" writes the configuration
    # value it got from its ConfigGettter to the shared memory.
    # checking its matches with the values set in the toml
    # config file
    d = SharedMemory.get("testf")
    assert d["c1"] == config["c1"]
    assert d["c2"] == config["c2"]


@pytest.mark.parametrize("runner_class", (TestProcessRunner, TestThreadRunner))
def test_basic_runner_factory(runner_class) -> None:
    """
    Test for the
    [nightskyrunner.factories.BasicRunnerFactory]() class.
    """

    config: Config = {"goodbye": "bye bye", "field": 1, "frequency": 1.0}
    factory = BasicRunnerFactory(runner_class, config)
    instance = factory.instantiate()
    assert type(instance) is runner_class
