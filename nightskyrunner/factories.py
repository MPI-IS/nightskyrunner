"""
Module defining the function dict_config_getter and the abstract 
class RunnerFactory.
"""

from typing import Any, Dict, Iterable, Optional, Type, cast

from .compare import compare_kwargs
from .config import Config
from .config_error import ConfigError
from .config_getter import ConfigGetter, FixedDict
from .dotted import DottedPath, get_from_dotted
from .runner import Runner
from .wait_interrupts import RunnerWaitInterruptors, get_interrupts


def _build_config_getter(
    class_path: DottedPath,
    args: Iterable[Any],
    kwargs: Dict[str, Any],
) -> ConfigGetter:
    # For example:
    #
    # "nightskyrunner.config_getter.DynamicTomlFile",  # dotted path to class
    # ["/path/to/toml/file"],  # args to pass to class constructor
    # {},  # kwargs to pass to class constructor
    #
    # returns:
    # DynamicTomlFile("/path/to/toml/file",**{})

    try:
        class_ = get_from_dotted(class_path)
    except ImportError as e:
        raise ConfigError(f"{class_path}: failed to import: {e}")

    if not issubclass(cast(type, class_), ConfigGetter):
        raise ConfigError(
            f"{class_.__name__}: must be a subclass of ConfigGetter"
        )
    if "template" in kwargs:
        raise ConfigError(
            f"{class_.__name__}: 'template' is a reserved keyword argument"
        )
    try:
        return class_(*args, **kwargs)
    except Exception as e:  # noqa: F841
        raise ConfigError(f"failed to instantiate {class_.__name__}: {e}")


def dict_config_getter(label: str, config: Dict[str, Any]) -> ConfigGetter:
    """
    Factory class for creating instances of ConfigGetter.

    Arguments:
      label: arbirary string, only used to produce more informative
        error messages.
      config: dictionary which accepts only the keys 'class', 'args' and
        'kwargs'. The value for class must be a dotted python path to
         a subclass of [config_getter.ConfigGetter](), args and kwargs
         suitable arguments for the constructor of this class.

    Raises:
      ConfigError if config contains unexpected key or incorrect values.
    """
    required_keys = ("class",)

    for rk in required_keys:
        if rk not in config:
            raise ConfigError(
                f"{label}: configuration is missing the key 'class'"
            )

    accepted_keys = ("class", "args", "kwargs")
    for k in config:
        if k not in accepted_keys:
            raise ConfigError(f"{label}: unexpected key '{k}'")

    try:
        args = config["args"]
    except KeyError:
        args = []
    if type(args) is not list:
        raise ConfigError(f"label/args: expected list, go {type(args)}")

    try:
        kwargs = config["kwargs"]
    except KeyError:
        kwargs = {}
    if type(args) is not list:
        raise ConfigError(f"label/kwargs: expected dict, go {type(args)}")

    return _build_config_getter(
        config["class"],
        args,
        kwargs,
    )


class RunnerFactory:
    """
    Abstract factory superclass for instantiating instances of
    [runner.Runner]().

    Arguments:
      name: name of the runner (arbirary string)
    """

    def __init__(self, name: str) -> None:
        self._name = name

    @property
    def name(self):
        return self._name

    def same(self, other: "RunnerFactory") -> bool:
        raise NotImplementedError

    def instantiate(
        self,
        core_frequency: float = 1.0 / 0.005,
        override: Optional[Config] = None,
    ) -> Runner:
        """
        Abstract method for instantiating a [runner.Runner]().

        Arguments:
          core_frequency: frequency at which the interrupts method will be called
            during sleep.
          override: entries of override will be overwrite any configuration value
            later on set by the user.
        """
        raise NotImplementedError()


class BasicRunnerFactory(RunnerFactory):
    """
    Runner factory that create instances of runners
    via their class and a [nightskyrunner.config_getter.FixedDict]()
    configuration getter.
    """

    def __init__(
        self,
        runner_class: Type[Runner],
        config: Config,
        runner_name: Optional[str] = None,
    ) -> None:
        if runner_name is None:
            runner_name = runner_class.__name__
        super().__init__(runner_name)
        self._runner_class = runner_class
        self._config_getter = FixedDict(config)

    def same(self, other: "RunnerFactory") -> bool:
        if other.__class__ != self.__class__:
            return False
        other = cast("BasicRunnerFactory", other)
        if self._runner_class != other._runner_class:
            return False
        if not compare_kwargs(
            self._config_getter.get(), other._config_getter.get()
        ):
            return False
        return True

    def instantiate(
        self,
        core_frequency: float = 1.0 / 0.005,
        override: Optional[Config] = None,
    ) -> Runner:
        """
        Returns an instance of the target runner.
        """
        interrupts = get_interrupts(self._name, self._config_getter)
        instance = self._runner_class(
            self._name,
            self._config_getter,
            interrupts=interrupts,
            core_frequency=core_frequency,
        )
        if override is not None:
            self._config_getter.set_override(override)
        return instance
