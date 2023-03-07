"""
Unit tests for the configcheck and configcheckers modules
"""

import pytest
import tempfile
import copy
from pathlib import Path
from nightskyrunner import config_check, config_checkers
from nightskyrunner.config_error import ConfigError, ConfigErrors


def test_is_checker_function():
    def good(a: str, b: int, c: int = 1) -> None:
        ...

    def bad1(a: int, b: int) -> None:
        ...

    def bad2(a: str, b: int = 1) -> None:
        ...

    def bad3(a: str, b: int, c: int) -> None:
        ...

    config_check.is_checker_function(good)

    for bad in (bad1, bad2, bad3):
        with pytest.raises(config_check.NotACheckerFunction):
            config_check.is_checker_function(bad)


def test_checker_methods():
    """
    Test the basic checkers:
    - isint
    - minmax
    - is_directory
    """

    for value in ("str", str, [1, 2], 1.3):
        with pytest.raises(ConfigError):
            config_checkers.isint("", value)

    with pytest.raises(ConfigError):
        config_checkers.minmax("", -1, vmin=0)
        config_checkers.minmax("", +1, vmax=0)

    with pytest.raises(ConfigError):
        p = Path("/not/existing/path")
        config_checkers.is_directory("", p, create=False)
