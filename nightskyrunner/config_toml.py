"""
[config_getter.ConfigGetter] and [manager.ManagerConfigGetter] are abstract classes
aiming at instantiating configuration.
This module defines the corresponding concrete subclasses that read the configuration
data from toml files.
"""

import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Type, Union, cast

import jinja2
import toml
import tomli

from .compare import compare_kwargs
from .config import Config
from .config_error import ConfigError
from .config_getter import ConfigGetter
from .dotted import DottedPath, get_from_dotted
from .factories import RunnerFactory, dict_config_getter
from .manager import ManagerConfigGetter
from .runner import Runner
from .shared_memory import DictProxy
from .wait_interrupts import (FileChangeInterrupt, RunnerWaitInterruptor,
                              RunnerWaitInterruptors, get_interrupts)

Vars = Optional[Union[Path, Dict[str, Any]]]


class TomlConfigError(Exception):
    """
    To be raised when the toml config
    file has unsupported key or value.
    """


class TomlRunnerFactory(RunnerFactory):
    # For example:
    #
    #  name = "my_runner"
    #  runner = "dotted.path.to.runner.class"
    #  config_getter_factory = TomlConfigGetterFactory(/path/to/toml)
    #
    # Prepare for the instantiation of the runner class
    # based on the provided configuration toml file
    # (which provides information for the related instance
    # of ConfigGetter

    def __init__(
        self,
        name: str,
        runner: Union[DottedPath, Type[Runner]],
        config_getter: Union[DottedPath, Type[ConfigGetter]],
        args: List[Any] = [],
        kwargs: Dict[str, Any] = {},
    ) -> None:
        super().__init__(name)
        self._frequency: Optional[float]
        self._runner_class: Type[Runner]
        if type(runner) is Type[Runner]:
            self._runner_class = runner  # type: ignore
        else:
            self._runner_class = get_from_dotted(runner)  # type: ignore
        self._config_getter_class: Type[ConfigGetter]
        if type(config_getter) is Type[ConfigGetter]:
            self._config_getter_class = config_getter  # type: ignore
        else:
            self._config_getter_class = get_from_dotted(config_getter)  # type: ignore
        self._args = args
        self._kwargs = kwargs

    def __str__(self) -> str:
        r: List[str] = []
        attrs = (
            "_name",
            "_runner_class",
            "_config_getter_class",
            "_args",
            "_kwargs",
        )
        for attr in attrs:
            r.append(f"{attr}:\t{getattr(self,attr)}")
        return "\n".join(r)

    def same(self, other: RunnerFactory) -> bool:
        if not self.__class__.__name__ == other.__class__.__name__:
            return False
        other = cast(TomlRunnerFactory, other)
        attrs = ("_name", "_runner_class", "_config_getter_class")
        for attr in attrs:
            if getattr(self, attr) != getattr(other, attr):
                return False
        if len(self._args) != len(other._args):
            return False
        for arg1, arg2 in zip(self._args, other._args):
            if arg1 != arg2:
                return False
        if not compare_kwargs(self._kwargs, other._kwargs):
            return False
        return True

    def instantiate(
        self,
        core_frequency: float = 1.0 / 0.005,
        override: Optional[Config] = None,
    ) -> Runner:
        """
        Return the instance of Runner
        """
        config_getter = self._config_getter_class(*self._args, **self._kwargs)

        interrupts = get_interrupts(self._name, config_getter)

        instance = self._runner_class(
            self._name,
            config_getter,
            interrupts=interrupts,
            core_frequency=core_frequency,
        )
        if override is not None:
            config_getter.set_override(override)
        return instance


def _toml_config_getter(
    filepath: Path, runner_name: Optional[str] = None
) -> ConfigGetter:
    if not filepath.is_file():
        raise ConfigError(f"failed to find the file {filepath}")

    try:
        with open(filepath, "rb") as f:
            content = tomli.load(f)
    except Exception as e:
        raise ConfigError(f"failed to parse the toml file {filepath}: {e}")

    if runner_name is not None:
        if runner_name not in content.keys():
            raise ConfigError(
                f"the toml file does not have a configuration for {runner_name}"
            )

    config_getter = dict_config_getter(str(filepath), content)
    return config_getter


class _TomlManagerConfigGetter(ManagerConfigGetter):
    # Superclass for TomlManagerConfigGetter (reads a
    # configuration toml file once at startup) and
    # DynamicTomlManagerConfigGetter (reads the toml
    # file at each iteration, in case the user
    # changed it)

    def __init__(self, filepath: Union[Path, str]) -> None:
        if isinstance(filepath, str):
            self._path = Path(filepath)
        else:
            self._path = filepath
        if not self._path.is_file():
            if (os.getcwd() / self._path).is_file():
                self._path = os.getcwd() / self._path
            else:
                raise FileNotFoundError(f"failed to find {self._path}")

    def _parse(self, name: str, config: Dict[str, Any]) -> TomlRunnerFactory:
        if "args" in config:
            args = config["args"]
        else:
            args = []
        if "kwargs" in config:
            kwargs = config["kwargs"]
        else:
            kwargs = {}
        return TomlRunnerFactory(
            name,
            config["class_runner"],
            config["class_config_getter"],
            args=args,
            kwargs=kwargs,
        )

    def parse(self) -> List[TomlRunnerFactory]:
        """
        Example of toml file:

        ```toml
        [runner1]
        class_runner = "nightskycam.AsiRunner"
        class_config_getter_factory = "nightskyrunner.factories.TomlConfigGetter"
        args = ["/path/to/toml"]
        kwargs = {}
        template = {
        "exposure" = 1.
        }
        ```
        """
        if not self._path.is_file():
            raise FileNotFoundError(
                f"failed to find the manager configuration file {self._path}"
            )

        with open(self._path, "rb") as f:
            try:
                content = tomli.load(f)
            except tomli.TOMLDecodeError as de:
                raise tomli.TOMLDecodeError(
                    f"failed to decode the toml content of {self._path}: {de}"
                )

        return [
            self._parse(runner_name, config) for runner_name, config in content.items()
        ]


class TomlManagerConfigGetter(_TomlManagerConfigGetter):
    """
    Subclass of [manager.ManagerConfigGetter] which
    returns instances of [factory.RunnerFactory] based on
    a toml configuration file.

    The toml configuration content should be like:

    ```toml
    [runner_name]
    class_runner = "package.module.RunnerClass"
    class_config_getter = "package.module.ConfigGetterClass"
    args = [arg1, arg2]
    [runner_name.kwargs]
    "kwarg1" =  value1
    ```

    for example:

    ```toml
    [process_runner]
    class_runner = "nightskyrunner.tests.TestProcessRunner"
    class_config_getter = "nightskyrunner.config_toml.DynamicTomlConfigGetter"
    args = ["process_runner.toml"]
    [process_runner.kwargs]
    "vars" =  "vars.toml"
    ```

    will produce an instance of [factory.RunnerFactory]() that will create instances
    of [tests.TestProcessRunner]() that will use an instance of [config_toml.DynamicTomlConfigGetter]()
    for getting its configuration values at realtime based on the content
    of the file process_runner.toml.

    """

    def __init__(self, path: Path) -> None:
        super().__init__(path)
        self._runner_factories = tuple(self.parse())

    def get(self) -> Tuple[RunnerFactory, ...]:
        return self._runner_factories


class DynamicTomlManagerConfigGetter(_TomlManagerConfigGetter):
    """
    Similar to [TomlManagerConfigGetter], but dynamic, i.e.
    the content of the toml configuration file will be periodically
    read, i.e. runners may be stopped or spawned if the content changes.

    For example, if the content of toml is:

    ```toml
    [process_runner]
    class_runner = "nightskyrunner.tests.TestProcessRunner"
    class_config_getter = "nightskyrunner.config_toml.DynamicTomlConfigGetter"
    args = ["process_runner.toml"]
    [process_runner.kwargs]
    "vars" =  "vars.toml"
    ```

    an instance of [tests.TestProcessRunner]() will be started.

    If later the content of the toml file is updated to:

    ```toml
    [process_runner]
    class_runner = "nightskyrunner.tests.TestProcessRunner"
    class_config_getter = "nightskyrunner.config_toml.DynamicTomlConfigGetter"
    args = ["process_runner.toml"]
    [process_runner.kwargs]
    "vars" =  "vars.toml"

    [thread_runner]
    class_runner = "nightskyrunner.tests.TestThreadRunner"
    class_config_getter = "nightskyrunner.config_toml.DynamicTomlConfigGetter"
    args = ["thread_runner.toml"]
    [thread_runner.kwargs]
    "vars" =  "vars.toml"
    ```

    then an instance of [tests.TestThreadRunner]() will also be started.
    """

    def __init__(self, path: Path) -> None:
        super().__init__(path)

    def get(self) -> Tuple[TomlRunnerFactory, ...]:
        return tuple(self.parse())


def _update_with_vars(vars: Vars, config_toml_path: Path) -> str:
    if vars is None:
        return config_toml_path.read_text()
    if isinstance(vars, Path) or isinstance(vars, str):
        toml_file = str(vars)
        try:
            data = toml.load(toml_file)
        except toml.decoder.TomlDecodeError as e:
            raise ConfigError(f"error while decoding {toml_file}: {e}")
    else:
        data = vars
    template_loader = jinja2.FileSystemLoader(
        searchpath=config_toml_path.parent.as_posix()
    )
    template_env = jinja2.Environment(loader=template_loader)
    template = template_env.get_template(config_toml_path.name)
    return template.render(data)


class StaticTomlConfigGetter(ConfigGetter):
    """
    Subclass of [config_getter.ConfigGetter]() that
    reads a configuration dictionary from a toml formated file.

    Arguments:
      path: path to the toml file
      override: see [config_getter.ConfigGetter]()

    Raises:
      FileNotFoundError if the file does not exists.
      TypeError if the file does not contain valid toml syntax
    """

    def __init__(
        self,
        path: Union[str, Path],
        override: Optional[Config] = None,
        vars: Vars = None,
    ) -> None:
        super().__init__(str(path), override=override)
        if isinstance(path, str):
            path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(f"failed to find configuration file {path}")
        self._path = path.resolve()
        self._config: Optional[Config] = None
        self._vars = vars

    def _get(self, kwargs: Dict[str, Any] = {}) -> Config:
        kw_vars = True
        if "vars" in kwargs.keys() and not kwargs["vars"]:
            kw_vars = False
        if self._config is None:
            if kw_vars and self._vars:
                content = _update_with_vars(self._vars, self._path)
            else:
                content = self._path.read_text()
            self._config = tomli.loads(content)
        return self._config


class DynamicTomlConfigGetter(ConfigGetter):
    """
    Subclass of [config_getter.ConfigGetter]() that
    reads a configuration dictionary from a toml formated file.
    Contrary to [StaticTomlConfigGetter]() which reads the toml
    file only once at construction, an instance of DynamicTomlConfigGetter
    reads the toml file at each call of its get function.

    Arguments:
      path: path to the toml file
      override: see [config_getter.ConfigGetter]()

    Raises:
      FileNotFoundError if the file does not exists.
      TypeError if the file does not contain valid toml syntax
    """

    def __init__(
        self,
        path: Union[str, Path],
        override: Optional[Config] = None,
        vars: Vars = None,
    ) -> None:
        super().__init__(str(path), override=override)
        if isinstance(path, str):
            path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(f"failed to find configuration file {path}")
        self._path = path.resolve()
        self._vars = vars

    def update(self, kwargs: DictProxy) -> None:
        """
        Overwrite the toml configuration file with
        a new file which path is given by the kwargs
        argument, i.e. ```kwargs["path"]``` is expected
        to be the absolute path to a toml file which will
        be copied over the original toml configuration file.
        """
        if "path" not in kwargs:
            return
        path = Path(kwargs["path"])
        del kwargs["path"]
        if not path.is_file():
            raise FileNotFoundError(
                str(
                    "failed to update toml configuration file path for "
                    f"{self._info}: file not found ({path})"
                )
            )
        shutil.move(str(path), str(self._path))

    def _get(self, kwargs: Dict[str, Any] = {}) -> Config:
        kw_vars = True
        if "vars" in kwargs.keys() and not kwargs["vars"]:
            kw_vars = False
        if kw_vars and self._vars:
            content = _update_with_vars(self._vars, self._path)
        else:
            content = self._path.read_text()
        try:
            return tomli.loads(content)
        except Exception as e:
            raise TomlConfigError(f"failed to parse {self._path}: {str(e)}")

    def wait_interrupt(self) -> Optional[RunnerWaitInterruptor]:
        """
        This method returns an instance of
        [wait_interrupts.FileChangeInterrupt](). Because of this,
        an instance of [runner.Runner]() using an instance of
        DynamicTomlConfigGetter as config_getter attribute will
        stop sleeping if the toml configuration file is updated.
        Why this is useful: if the original content of the toml file
        dictates a low frequency for the iteration of the runner
        (e.g. one iteration per hour) and the toml file is updated
        to a higher frequency (e.g. one iteration per minute),
        the runner could have sleep up to one hour before reading
        its configuration file again and adapt the higher frequency.
        Thanks to the interrupt returned by this function, the
        higher frequency will be applied without the long wait.

        Note: developpers do not need to call this method. It
        will be called under the wood by instances of [factories.RunnerFactory]()
        when creating new instances of [runner.Runner]().
        """
        return FileChangeInterrupt(self._path)
