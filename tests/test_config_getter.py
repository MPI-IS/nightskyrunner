"""
Tests the config_getter module
"""

import copy
import tempfile
from pathlib import Path
from typing import Generator

import pytest
import tomli_w

from nightskyrunner.config import Config
from nightskyrunner.config_error import ConfigError
from nightskyrunner.config_toml import (DynamicTomlConfigGetter,
                                        StaticTomlConfigGetter)


@pytest.fixture
def get_tmp(request, scope="function") -> Generator[Path, None, None]:
    """
    Returns a temporary directory path
    """
    tmp_dir_ = tempfile.TemporaryDirectory()
    tmp_dir = Path(tmp_dir_.name)
    yield tmp_dir
    tmp_dir_.cleanup()


@pytest.fixture
def get_config(request, scope="function") -> Generator[Config, None, None]:
    """
    Returns a configuration template
    """
    config: Config = {"a": 1, "b": 10, "c": {"c1": -1, "c2": 3}}
    yield config


def test_static_toml(get_tmp, get_config) -> None:
    """
    Unit test for StaticTomlConfigGetter
    """

    config = get_config

    tmp_dir = get_tmp
    path = tmp_dir / "test.toml"

    with open(path, "wb") as f:
        tomli_w.dump(config, f)
    conf_getter = StaticTomlConfigGetter(path)
    config_ = conf_getter.get()
    assert config_["a"] == 1
    assert config_["c"]["c2"] == 3

    override: Config = {"a": 2, "c": {"c1": 4}}
    conf_getter = StaticTomlConfigGetter(path, override)
    config_ = conf_getter.get()
    assert config_["a"] == 2
    assert config_["b"] == 10
    assert config_["c"]["c1"] == 4
    assert config_["c"]["c2"] == 3


def test_dynamic_toml(get_tmp, get_config) -> None:
    """
    Unit test for DynamicTomlConfigGetter
    """

    config = get_config

    tmp_dir = get_tmp
    path = tmp_dir / "test.toml"

    with open(path, "wb") as f:
        tomli_w.dump(config, f)
    conf_getter = DynamicTomlConfigGetter(path)
    config_ = conf_getter.get()
    assert config_["a"] == 1
    assert config_["c"]["c2"] == 3

    config["c"]["c2"] = 6
    with open(path, "wb") as f:
        tomli_w.dump(config, f)
    config_ = conf_getter.get()
    assert config_["c"]["c2"] == 6


def test_config_with_vars(get_tmp) -> None:
    vars = {"value1": 1, "value2": '"v2"', "value3": 3}

    config = {
        "t1": {"t11": 11, "t12": "{{ value1 }}"},
        "t2": "{{ value2 }}",
        "t3": "{{ value3 }}",
        "t4": 4,
    }

    secret_path = get_tmp / "vars.toml"
    config_path = get_tmp / "config.toml"

    with open(str(secret_path), "wb") as f:
        tomli_w.dump(vars, f)

    with open(str(config_path), "wb") as f:
        tomli_w.dump(config, f)

    with open(str(config_path), "r") as f:
        content = f.read()
        content = content.replace('"{{', "{{")
        content = content.replace('}}"', "}}")

    with open(str(config_path), "w") as f:
        f.write(content)

    config_getter = StaticTomlConfigGetter(config_path, vars=secret_path)

    config = config_getter.get()

    assert config["t1"]["t11"] == 11  # type: ignore
    assert config["t1"]["t12"] == 1  # type: ignore
    assert config["t2"] == "v2"
    assert config["t3"] == 3
    assert config["t4"] == 4
