import pytest
from nightskyrunner.config_error import ConfigErrors, ConfigError
from nightskyrunner.factories import (
    get_from_dotted,
    _check_kwargs,
    _configured_check_function
)


def test_method_dotted():

    path = "nightskyrunner.factories.get_from_dotted"
    method = get_from_dotted(path)
    assert method.__name__ == "get_from_dotted"

    prefixes = (
        "nightskyrunner.whatever1",
        "nightskyrunner.factories",
        "nightskyrunner.whatever2",
    )
    method = get_from_dotted("get_from_dotted",prefixes)
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
    class_ = get_from_dotted("ConfigError",prefixes)
    assert class_.__name__ == "ConfigError"


def test_ext_lib_dotted():

    path = "pathlib.Path"
    class_ = get_from_dotted(path)
    assert class_.__name__ == "Path"


def test_check_kwargs():

    def A(a,b,k1=1, k2=2):
        pass

    with ConfigErrors("test1"):

        _check_kwargs(A,{"k1":1,"k2":2})
        assert not ConfigErrors.has_error()
        _check_kwargs(A,{"k1":1})
        assert not ConfigErrors.has_error()

    with pytest.raises(ConfigError):
        with ConfigErrors("test2"):
            _check_kwargs(A,{"not_existing_kwargs":1})
            assert ConfigErrors.has_error()

def test_configured_check_function():

    modules = [
        "nightskyrunner.config_checkers",
        "another"
    ]
    
    function = "isint"
    kwargs = {}
    with ConfigErrors("test3"):
        _configured_check_function(
            modules, function, kwargs
        )
    
    function = "minmax"
    kwargs = {"vmin":-1,"vmax":+1}
    with ConfigErrors("test4"):
        _configured_check_function(
            modules, function, kwargs
        )
        print(ConfigErrors.get())

        
