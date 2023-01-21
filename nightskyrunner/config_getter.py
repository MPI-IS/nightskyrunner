"""
Module for ConfigGetter and related sub-classes.
An instance of ConfigurationGetter as a 'get' method which returns a configuration dict.
(see [config.Config](Config)).
"""

from typing import Any, Callable, Dict, Optional

from .config import Config
from .config_error import ConfigError
from .shared_memory import DictProxy


def _override(c1: Config, c2: Config) -> None:
    # If c2 has keys also present in c1, the corresponding
    # value in c1 will be replaced by the corresponding value
    # in c2. If the value is c2, a recursive call is made.
    for key, value2 in c2.items():
        try:
            value1 = c1[key]
        except KeyError:
            raise ConfigError(
                "can not override (no such configuration key)",
            )
        if type(value2) is dict:
            if not type(value1) is dict:
                raise ConfigError(
                    "can not override (expected a dict)",
                )
            _override(value1, value2)
        else:
            c1[key] = value2


class ConfigGetter:
    """
    Abstract super class for objects for instanciating
    [config.Config](Config) dictionaries.
    Instances of [runner.Runner](Runner) iterate function
    will access their configuration runner attribute to
    access configuration value during runtime.

    Args:
      info: an arbirary string
      override: if provided, corresponding values will be replaced
        in configuration dict before being returned by the get function.
    """

    def __init__(
        self,
        info: str,
        override: Optional[Config] = None,
    ) -> None:
        self._info = info
        self._override = override

    def update(self, kwargs: DictProxy) -> None:
        # update to be (optionally) set by subclasses
        ...

    def wait_interrupt(self) -> Optional[Callable[[], bool]]:
        return None

    def set_override(self, override: Config) -> None:
        """
        Overwrite the 'override' configuration provided
        to the constructor
        """
        self._override = override

    def _get(self, kwargs: Dict[str, Any]) -> Config:
        raise NotImplementedError()

    def get(self, **kwargs) -> Config:
        """
        Returns a configuration dictionary.
        If an 'override' has been provided to the constructor, updates
        the configuration accordingly before returning it.
        """
        config = self._get(kwargs)
        if self._override is not None:
            _override(config, self._override)
        return config


class FixedDict(ConfigGetter):
    """
    Returns the configuration dictionary that was
    passed at it as arguments, possibly updated by
    the override configuration.
    """

    def __init__(
        self,
        config: Config,
        override: Optional[Config] = None,
    ) -> None:
        super().__init__(str(config), override=override)
        self._config = config

    def _get(self, kwargs={}):
        return self._config
