"""
Module for ConfigGetter and related sub-classes.
An instance of ConfigurationGetter as a 'get' method which returns a configuration dict.
"""

import toml
from typing import Optional
from pathlib import Path
from .config import Config
from .configcheck import ConfigurationValueError, ConfigTemplate, check_configuration


def _override(c1: Config, c2: Config) -> None:
    for key, value2 in c2.items():
        try:
            value1 = c1[key]
        except KeyError:
            raise ConfigurationValueError(
                key, None, "can not override (no such configuration field)"
            )
        if type(value2) == dict:
            if not type(value1) == dict:
                raise ConfigurationValueError(
                    key, None, "can not override (expected a dict)"
                )
            _override(value1, value2)
        else:
            c1[key] = value2


class ConfigGetter:
    """
    Abstract super class for objects reading configuration dict.

    Args:
      template: if provided as argument, configuration dict will be
        checked against it before being returned
      override: if provided, corresponding values will be replaced
        in configuration dict before being returned
    """

    def __init__(
        self,
        template: Optional[ConfigTemplate] = None,
        override: Optional[Config] = None,
    ) -> None:
        self._template = template
        self._override = override

    def _get(self) -> Config:
        raise NotImplementedError()

    def get(self) -> Config:
        """
        Returns a configuration dictionary.
        If a 'template' has been provided to the constructor, checks
        the configuration against it before returning it.
        If an 'override' has been provided to the constructor, updates
        the configuration accordingly before returning it.

        Raises:
          A ConfigurationValueError if the configuration is not valid
            according to the template; or if there is a mismatch between
            the override dict and the configuration.
        """
        config = self._get()
        if self._override is not None:
            _override(config, self._override)
        if self._template is not None:
            check_configuration(self._template, config)
        return config


class FixedDictConfigGetter(ConfigGetter):
    """
    Returns the configuration dictionary that was
    passed at it as arguments, possibly updated by
    the override configuration.
    """

    def __init__(
        self,
        config: Config,
        template: Optional[ConfigTemplate] = None,
        override: Optional[Config] = None,
    ) -> None:
        super().__init__(template=template, override=override)
        self._config = config

    def _get(self):
        return self._config


class StaticTomlFile(ConfigGetter):
    """
    Returns configuration dict based on a toml formated file.

    Raises:
      FileNotFoundError if the file does not exists.
      TypeError if the file does not contain valid toml syntax
    """

    def __init__(
        self,
        path: str | Path,
        template: Optional[ConfigTemplate] = None,
        override: Optional[Config] = None,
    ) -> None:
        super().__init__(template=template, override=override)
        if isinstance(path, str):
            path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(f"failed to find configuration file {path}")
        self._path = path
        self._config: Config = toml.loads(path.read_text())

    def _get(self) -> Config:
        return self._config


class DynamicTomlFile(ConfigGetter):
    """
    Returns configuration dict based on a toml formated file.
    Re-read the file at each call of 'get'.

    Raises:
      FileNotFoundError if the file does not exists.
      TypeError if the file does not contain valid toml syntax
    """

    def __init__(
        self,
        path: str | Path,
        template: Optional[ConfigTemplate] = None,
        override: Optional[Config] = None,
    ) -> None:
        super().__init__(template=template, override=override)
        if isinstance(path, str):
            path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(f"failed to find configuration file {path}")
        self._path = path

    def _get(self) -> Config:
        return toml.loads(self._path.read_text())
