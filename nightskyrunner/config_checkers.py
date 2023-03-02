import sys
from typing import Any, Iterable
from pathlib import Path
from .config_check import checker
from .config_error import ConfigError


def _wrong_type(name: str, value: Any, types: Iterable[type]) -> None:
    if any([type(value) == t for t in types]):
        return None
    type_str = ", ".join([str(t) for t in types])
    raise ConfigValueError(
        name, value, f"wrong type (got {type(value)}, expect {type_str})"
    )


@checker
def isint(name: str, value: Any) -> None:
    """
    Raises a ConfigurationError is value is not an integer.
    """
    return _wrong_type(name, value, (int,))


@checker
def minmax(name: str, value: Any, vmin=-sys.maxsize, vmax=sys.maxsize) -> None:
    """
    Raises a ConfigurationError if value is not in the internval vmin, vmax.
    """
    if value < vmin:
        raise ConfigValueError(name, value, f"value should be in [{vmin}, {vmax}]")
    if value > vmax:
        raise ConfigValueError(name, value, f"value should be in [{vmin}, {vmax}]")


@checker
def is_directory(name: str, value: Any, create: bool = False) -> None:
    """ "
    Raises a ConfigurationError if value is not a directory.
    If create is True, this method will attempt to create the directory
    if it does not exists.
    """
    if isinstance(value, str):
        value = Path(value)
    if not isinstance(value, Path):
        _wrong_type(name, value, (str, type(Path)))
    if not value.exists():
        if create:
            value.mkdir(parents=True)
            return
        raise ConfigValueError(name, value, "directory not found")
    if not value.is_dir():
        raise ConfigValueError(name, value, "not a directory")
