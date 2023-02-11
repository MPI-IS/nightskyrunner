"""
Unit tests for the configcheck and configcheckers modules
"""

import pytest
import tempfile
import copy
from pathlib import Path
from nightskyrunner import configcheck, configcheckers


def test_configuration_value_error():
    """
    Test the class ConfigurationValueError
    """
    error1 = configcheck.ConfigurationValueError("error1", 1, "error message 1")
    error2 = configcheck.ConfigurationValueError("error2", 2, "error message 2")

    error1.add(error2)

    for index, (error, value, message) in enumerate(error1):
        assert error == f"error{index+1}"
        assert value == index + 1
        assert message == f"error message {index+1}"


def test_checker_methods():
    """
    Test the basic checkers:
    - isint
    - minmax
    - is_directory
    """

    for value in ("str", str, [1, 2], 1.3):
        with pytest.raises(configcheck.ConfigurationValueError):
            configcheckers.isint()("", value)

    with pytest.raises(configcheck.ConfigurationValueError):
        configcheckers.minmax(vmin=0)("", -1)
        configcheckers.minmax(vmax=0)("", +1)

    with pytest.raises(configcheck.ConfigurationValueError):
        p = Path("/not/existing/path")
        configcheckers.is_directory(create=False)("", p)

    configcheckers.isint()("", 1)
    configcheckers.minmax(vmin=0, vmax=2)("", 1)

    with tempfile.TemporaryDirectory() as tmp_dir_:
        tmp_dir = Path(tmp_dir_)
        configcheckers.is_directory(create=False)("", tmp_dir)
        extended_tmp_dir = tmp_dir / "created"
        configcheckers.is_directory(create=True)("", extended_tmp_dir)


def test_check_configuration():

    with tempfile.TemporaryDirectory() as tmp_dir_:

        tmp_dir = Path(tmp_dir_)

        template: configcheck.ConfigTemplate = {
            "a": (configcheckers.isint(), configcheckers.minmax(vmin=-1, vmax=1)),
            "b": (configcheckers.isint(),),
            "c": (configcheckers.is_directory(create=False),),
            "d": (configcheckers.is_directory(create=True),),
            "e": [],
        }

        config_ok: configcheck.Config = {
            "a": 1,
            "b": 20,
            "c": tmp_dir,
            "d": tmp_dir / "sub",
            "e": 1.1,
        }
        configcheck.check_configuration(template, config_ok)

        config1: configcheck.Config = copy.deepcopy(config_ok)
        config1["a"] = 10
        with pytest.raises(configcheck.ConfigurationValueError):
            configcheck.check_configuration(template, config1)

        config2: configcheck.Config = copy.deepcopy(config_ok)
        config2["a"] = 1.2
        with pytest.raises(configcheck.ConfigurationValueError):
            configcheck.check_configuration(template, config2)

        config3: configcheck.Config = copy.deepcopy(config_ok)
        config3["b"] = 1.2
        config3["c"] = Path("/no/such/path")
        with pytest.raises(configcheck.ConfigurationValueError):
            configcheck.check_configuration(template, config3)

        config4: configcheck.Config = copy.deepcopy(config_ok)
        config4["other"] = 1
        with pytest.raises(configcheck.ConfigurationValueError):
            configcheck.check_configuration(template, config4)

        config5: configcheck.Config = copy.deepcopy(config_ok)
        del config5["b"]
        with pytest.raises(configcheck.ConfigurationValueError):
            configcheck.check_configuration(template, config5)
