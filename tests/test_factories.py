import pytest
import tempfile
import toml
from pathlib import Path
from typing import Generator
from nightskyrunner.config_error import ConfigErrors, ConfigError
from nightskyrunner.factories import (
    get_from_dotted,
    _configured_check_function,
    _field_template_config,
    _get_config_template,
    build_config_getter,
    toml_config_getter,
)
from nightskyrunner.config_check import check_configuration
from nightskyrunner.config_getter import FixedDict, DynamicTomlFile


@pytest.fixture
def reset_config_errors(request, scope="function") -> Generator[None, None, None]:
    yield None
    ConfigErrors.clear()


@pytest.fixture
def get_tmp(request, scope="function") -> Generator[Path, None, None]:
    """
    Returns a temporary directory path
    """
    tmp_dir_ = tempfile.TemporaryDirectory()
    tmp_dir = Path(tmp_dir_.name)
    yield tmp_dir
    tmp_dir_.cleanup


def test_method_dotted():

    path = "nightskyrunner.factories.get_from_dotted"
    method = get_from_dotted(path)
    assert method.__name__ == "get_from_dotted"

    prefixes = (
        "nightskyrunner.whatever1",
        "nightskyrunner.factories",
        "nightskyrunner.whatever2",
    )
    method = get_from_dotted("get_from_dotted", prefixes)
    assert method.__name__ == "get_from_dotted"


def test_class_dotted():

    path = "nightskyrunner.config_error.ConfigError"
    class_ = get_from_dotted(path)
    assert class_.__name__ == "ConfigError"

    prefixes = (
        "nightskyrunner.whatever1",
        "nightskyrunner.config_error",
        "nightskyrunner.whatever2",
    )
    class_ = get_from_dotted("ConfigError", prefixes)
    assert class_.__name__ == "ConfigError"


def test_ext_lib_dotted():

    path = "pathlib.Path"
    class_ = get_from_dotted(path)
    assert class_.__name__ == "Path"


def test_configured_check_function(reset_config_errors):

    modules = ["nightskyrunner.config_checkers", "another"]

    function = "isint"
    kwargs = {}
    with ConfigErrors("test"):
        _configured_check_function(modules, function, kwargs)
        assert not ConfigErrors.has_error()

    function = "minmax"
    kwargs = {"vmin": -1, "vmax": +1}
    with ConfigErrors("test"):
        _configured_check_function(modules, function, kwargs)
        assert not ConfigErrors.has_error()

    with pytest.raises(ConfigError):

        def A(a=1):
            return a

        kwargs = {"a": 1}
        with ConfigErrors("test"):
            _configured_check_function(modules, A, kwargs)

    function = "minmax"
    kwargs = {"not_existing_kwarg": -1, "vmax": +1}
    with pytest.raises(ConfigError):
        with ConfigErrors("test"):
            _configured_check_function(modules, function, kwargs)

    modules = ["pathlib", "another.module"]
    with pytest.raises(ConfigError):
        function = "minmax"
        kwargs = {"vmin": -1, "vmax": +1}
        with ConfigErrors("test"):
            _configured_check_function(modules, function, kwargs)


def test_field_template_config(reset_config_errors):

    modules = ["nightskyrunner.config_checkers", "another.module"]
    checkers = {"minmax": {"vmin": -2, "vmax": +3}, "isint": {}}
    functions = _field_template_config(modules, checkers)
    good_values = {"good1": 2, "good2": -1}
    bad_values = {"bad1": -3, "bad2": 1.1}
    with ConfigErrors("test"):
        [f(name, value) for f in functions for name, value in good_values.items()]
        assert not ConfigErrors.has_error()

    for name, value in bad_values.items():
        with pytest.raises(ConfigError):
            with ConfigErrors("test"):
                [f(name, value) for f in functions]


def test_get_config_template(reset_config_errors):

    modules = ["another.module", "nightskyrunner.config_checkers"]
    fields = {
        "field1": {"minmax": {"vmin": -1, "vmax": +1}, "isint": {}},
        "field2": {"isint": {}},
    }

    template = _get_config_template(modules, fields)

    good_config = {"field1": 0, "field2": 12}

    bad_config1 = {"field1": -2, "field2": 0}

    bad_config2 = {"field1": 0, "field2": 1.1}

    with ConfigErrors("test"):
        check_configuration(template, good_config)
        assert not ConfigErrors.has_error()

    for bad_config in (bad_config1, bad_config2):
        with pytest.raises(ConfigError):
            with ConfigErrors("test"):
                check_configuration(template, bad_config)


def test_build_config_getter(reset_config_errors):

    class_path = "nightskyrunner.config_getter.FixedDict"
    fixed_config = {"field1": 0, "field2": 12}
    args = (fixed_config,)
    kwargs = {}
    modules = ["another.module", "nightskyrunner.config_checkers"]
    fields = {
        "field1": {"minmax": {"vmin": -1, "vmax": +1}, "isint": {}},
        "field2": {"isint": {}},
    }

    with ConfigErrors("test"):

        config_getter = build_config_getter(class_path, args, kwargs, modules, fields)
        assert isinstance(config_getter, FixedDict)
        config = config_getter.get()
        for k, v in config.items():
            assert fixed_config[k] == v
        for k, v in fixed_config.items():
            assert config[k] == v

        kwargs = {"override": {"field2": -6}}
        config_getter = build_config_getter(class_path, args, kwargs, modules, fields)
        assert isinstance(config_getter, FixedDict)
        config = config_getter.get()
        assert config["field1"] == 0
        assert config["field2"] == -6

        assert not ConfigErrors.has_error()

    fixed_config = {
        "field1": 6,  # according to "fields" should be between -1 and 1
        "field2": 12,
    }
    args = (fixed_config,)
    with pytest.raises(ConfigError):
        with ConfigErrors("test"):
            config_getter = build_config_getter(
                class_path, args, kwargs, modules, fields
            )
            assert isinstance(config_getter, FixedDictConfigGetter)
            config = config_getter.get()


def test_toml_config_getter(reset_config_errors, get_tmp):

    tmp_dir = get_tmp

    config_path = tmp_dir / "config.toml"
    config = {"field1": 0, "field2": 12}
    with open(config_path, "w") as f:
        toml.dump(config, f)

    main_path = tmp_dir / "main.toml"
    toml_content = {
        "class": "nightskyrunner.config_getter.DynamicTomlFile",
        "args": [f"{config_path}"],
        "kwargs": {},
        "template": {
            "modules": ["another.module", "nightskyrunner.config_checkers"],
            "field1": {"minmax": {"vmin": -1, "vmax": +1}, "isint": {}},
            "field2": {"isint": {}},
        },
    }
    with open(main_path, "w") as f:
        toml.dump(toml_content, f)

    config_getter = toml_config_getter(main_path)
    assert isinstance(config_getter, DynamicTomlFile)
    get_config = config_getter.get()
    assert get_config["field1"] == 0
    assert get_config["field2"] == 12
