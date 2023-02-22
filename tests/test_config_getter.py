"""
Unit tests for the config_getter module
"""

import pytest
import tempfile
import toml
import copy
from pathlib import Path
from typing import Generator
from nightskyrunner.config_getter import StaticTomlFile, DynamicTomlFile
from nightskyrunner.config import Config
from nightskyrunner.configcheck import ConfigTemplate, ConfigValueError
from nightskyrunner.configcheckers import isint


@pytest.fixture
def get_tmp(request, scope="function") -> Generator[Path, None, None]:
    """
    Returns a temporary directory path
    """
    tmp_dir_ = tempfile.TemporaryDirectory()
    tmp_dir = Path(tmp_dir_.name)
    yield tmp_dir
    tmp_dir_.cleanup


@pytest.fixture
def get_config(
    request, scope="function"
) -> Generator[tuple[ConfigTemplate, Config], None, None]:
    """
    Returns a configuration template and a corresponding
    valid configuration
    """
    checks = (isint(),)
    config_template: ConfigTemplate = {
        "a": checks,
        "b": checks,
        "c": {"c1": checks, "c2": checks},
    }
    config: Config = {"a": 1, "b": 10, "c": {"c1": -1, "c2": 3}}
    yield config_template, config


def test_static_toml(get_tmp, get_config):
    """
    Unit test for StaticTomlFile
    """

    config_template, config = get_config

    tmp_dir = get_tmp
    path = tmp_dir / "test.toml"

    with open(path, "w") as f:
        toml.dump(config, f)
    conf_getter = StaticTomlFile(path, config_template)
    config_ = conf_getter.get()
    assert config_["a"] == 1
    assert config_["c"]["c2"] == 3

    override: Config = {"a": 2, "c": {"c1": 4}}
    conf_getter = StaticTomlFile(path, config_template, override)
    config_ = conf_getter.get()
    assert config_["a"] == 2
    assert config_["b"] == 10
    assert config_["c"]["c1"] == 4
    assert config_["c"]["c2"] == 3

    wrong_config = copy.deepcopy(config)
    wrong_config["a"] = 1.1
    with open(path, "w+") as f:
        toml.dump(wrong_config, f)
    conf_getter = StaticTomlFile(path, config_template)
    with pytest.raises(ConfigValueError):
        conf_getter.get()


def test_dynamic_toml(get_tmp, get_config):
    """
    Unit test for DynamicTomlFile
    """

    config_template, config = get_config

    tmp_dir = get_tmp
    path = tmp_dir / "test.toml"

    with open(path, "w") as f:
        toml.dump(config, f)
    conf_getter = DynamicTomlFile(path, config_template)
    config_ = conf_getter.get()
    assert config_["a"] == 1
    assert config_["c"]["c2"] == 3

    config["c"]["c2"] = 6
    with open(path, "w") as f:
        toml.dump(config, f)
    config_ = conf_getter.get()
    assert config_["c"]["c2"] == 6
