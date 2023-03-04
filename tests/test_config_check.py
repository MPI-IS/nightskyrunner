"""
Unit tests for the configcheck and configcheckers modules
"""

import pytest
import tempfile
import copy
from pathlib import Path
from nightskyrunner import confi_check, config_checkers
from nightskyrunner.config_error import ConfigError, ConfigErrors


def test_configuration_value_error():
    """
    Test the class ConfigValueError
    """
    error1 = config_check.ConfigValueError("error1", 1, "error message 1")
    error2 = config_check.ConfigValueError("error2", 2, "error message 2")

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
        with pytest.raises(config_check.ConfigValueError):
            config_checkers.isint()("", value)

    with pytest.raises(config_check.ConfigValueError):
        config_checkers.minmax(vmin=0)("", -1)
        config_checkers.minmax(vmax=0)("", +1)

    with pytest.raises(config_check.ConfigValueError):
        p = Path("/not/existing/path")
        config_checkers.is_directory(create=False)("", p)

    config_checkers.isint()("", 1)
    config_checkers.minmax(vmin=0, vmax=2)("", 1)

    with tempfile.TemporaryDirectory() as tmp_dir_:
        tmp_dir = Path(tmp_dir_)
        config_checkers.is_directory(create=False)("", tmp_dir)
        extended_tmp_dir = tmp_dir / "created"
        config_checkers.is_directory(create=True)("", extended_tmp_dir)


def test_check_configuration():

    with tempfile.TemporaryDirectory() as tmp_dir_:

        tmp_dir = Path(tmp_dir_)

        template: config_check.ConfigTemplate = {
            "a": (config_checkers.isint(), config_checkers.minmax(vmin=-1, vmax=1)),
            "b": (config_checkers.isint(),),
            "c": (config_checkers.is_directory(create=False),),
            "d": (config_checkers.is_directory(create=True),),
            "e": [],
        }

        config_ok: config_check.Config = {
            "a": 1,
            "b": 20,
            "c": tmp_dir,
            "d": tmp_dir / "sub",
            "e": 1.1,
        }
        config_check.check_configuration(template, config_ok)

        config1: config_check.Config = copy.deepcopy(config_ok)
        config1["a"] = 10
        with pytest.raises(config_check.ConfigValueError):
            config_check.check_configuration(template, config1)

        config2: config_check.Config = copy.deepcopy(config_ok)
        config2["a"] = 1.2
        with pytest.raises(config_check.ConfigValueError):
            config_check.check_configuration(template, config2)

        config3: config_check.Config = copy.deepcopy(config_ok)
        config3["b"] = 1.2
        config3["c"] = Path("/no/such/path")
        with pytest.raises(config_check.ConfigValueError):
            config_check.check_configuration(template, config3)

        config4: config_check.Config = copy.deepcopy(config_ok)
        config4["other"] = 1
        with pytest.raises(config_check.ConfigValueError):
            config_check.check_configuration(template, config4)

        config5: config_check.Config = copy.deepcopy(config_ok)
        del config5["b"]
        with pytest.raises(config_check.ConfigValueError):
            config_check.check_configuration(template, config5)


def test_recursive_check_configuration():

    sub1_template = config_check.ConfigTemplate = {
        "s11": (config_checkers.isint(),),
        "s12": (config_checkers.isint(),),
    }

    sub2_template = config_check.ConfigTemplate = {
        "s21": (config_checkers.isint(),),
        "s22": sub1_template,
        "s23": (config_checkers.isint(),),
    }

    sub3_template = config_check.ConfigTemplate = {
        "s31": (config_checkers.isint(), config_checkers.minmax(vmin=-1, vmax=1)),
    }

    template: config_check.ConfigTemplate = {
        "a": (config_checkers.isint(), config_checkers.minmax(vmin=-1, vmax=1)),
        "s2": sub2_template,
        "s3": sub3_template,
        "b": (config_checkers.isint(),),
    }

    config_ok: config_check.Config = {
        "a": 1,
        "s2": {
            "s21": 4,
            "s22": {
                "s11": 2,
                "s12": -8,
            },
            "s23": 0,
        },
        "s3": {"s31": 0},
        "b": 100,
    }
    config_check.check_configuration(template, config_ok)

    config_not_ok1: config_check.Config = {
        "a": 1,
        "s2": {
            "s21": 4,
            "s22": {
                "s11": 2.1,  # !
                "s12": -8,
            },
            "s23": 0,
        },
        "s3": {"s31": 0},
        "b": 100,
    }

    config_not_ok2: config_check.Config = {
        "a": 1,
        "s2": {
            "s21": 4,
            "s22": 1,  # !
        },
        "s23": 0,
        "s3": {"s31": 0},
        "b": 100,
    }

    config_not_ok3: config_check.Config = {
        "a": 1,
        "s2": {
            "s21": 4,
            "s22": {
                "s11": 2,
                "s12": -8,
            },
            "s23": 0,
        },
        "s3": {"s31": 0},
        "b": 100.1,  # !
    }

    for config in (config_not_ok1, config_not_ok2, config_not_ok3):
        with pytest.raises(config_check.ConfigValueError):
            config_check.check_configuration(template, config)
