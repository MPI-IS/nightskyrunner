"""
Module implementing code for checking if a configuration dictionary is valid under rules
specified by the developer.

Developers can create a template expressing the rules a configuration dictionary must
enforce to be valid, e.g.

``` python
    @checker
    def is_above(name: str, value: Any, threshold=1.0)->None:
        if value<threshold:
            raise ConfigValueError(name, value, f"under the threshold {threshold}")

    @checker is_float(name: str, value: float)->None:
        if not isinstance(float, value):
            raise ConfigValueError(name, value, f"value must be a float")

    template = {
        "field1": (is_float(), is_above(threshold=2.)),
        "field2": (is_float(),)
    }

    config_ok = {
        "field1": 3.0,
        "field2": 1.3
    }
    check_configuration(template, config_ok)

    # raises a ConfigValueError:
    config_not_ok = {
        "field1": -1.0,  # below threshold of 2 !
        "field2": 1.3
    }
    check_configuration(template, config_not_ok)
```

See the configcheckers module for reusable checker methods.
"""

import inspect
from typing import Any, Iterable, Callable, Union
from .config import Config
from .config_error import ConfigError, ConfigErrors


CheckerMethod = Callable[[str, Any], None]
"""
Interface for a checker method.

Args:
  name: name of the configuration fields
  value: value entered by the user
  kwargs: configuration of the checker method

Raises:
  ConfigurationError if the value entered by the user
    is not suitable
"""


class NotACheckerFunction(Exception):
    """
    To be raised if a function is expected to be a CheckerMethod, but is not
    """

    def __init__(self, function: Callable, issue: str) -> None:
        self._function = function
        self._issue = issue

    def __str__(self) -> str:
        return str(
            f"{self._function.__name__} is not a valid configuration "
            f"checker function: {self._issue}"
        )


def is_checker_function(function: Callable) -> None:
    """
    Raises a NotACheckerFunction if the function does not
    has the signature of a CheckerMethod, i.e. Callable[[str, Any], None]
    """
    # a checker function must have two positional, first being a str
    # other arguments have to be keyword based
    parameters = inspect.signature(function).parameters
    for index, key in enumerate(parameters.keys()):
        value = parameters[key]
        if index == 0:
            if value.default != inspect._empty:
                raise NotACheckerFunction(
                    function, "first argument should be positional (and a string)"
                )
            if value.annotation != str:
                raise NotACheckerFunction(function, "first argument should be a string")
        elif index == 1:
            if value.default != inspect._empty:
                raise NotACheckerFunction(
                    function, "second argument should be positional"
                )
        else:
            if value.default == inspect._empty:
                raise NotACheckerFunction(
                    function, "only the first two arguments should be positional"
                )


def are_supported_kwargs(function: CheckerMethod, kwargs: dict[str, Any]) -> None:
    """
    Raises a ConfigError if any of the kwargs is not supported by the function
    """
    error = ConfigError()
    skwargs = [
        key
        for key, value in inspect.signature(function).parameters.items()
        if value.default != inspect._empty
    ]
    # checking the kwargs passed by the users match the
    # supported keyword arguments
    for kwarg in kwargs.keys():
        if kwarg not in skwargs:
            error.add(
                message=str(
                    f"{function.__name__}: {kwarg} is not a supported argument "
                    f"(supported: {','.join([k for k in skwargs])})"
                )
            )
    if error.has_error():
        raise error


ConfigTemplate = dict[str, Iterable[CheckerMethod] | "ConfigTemplate"]
"""
A template is a dictionary allowing the developer to specify the
criterion a configuration dictionary must apply to be valid.
"""

CheckersTemplate = list[tuple[str, dict[str, Any]]]
"""
List of checker functions associated with their kwargs, e.g:
```
[ ("minmax",{minv=-1,maxv:+1}), ("isint":{}) ]
```
"""

ConfigTemplateSpec = dict[str, Union[CheckersTemplate, "ConfigTemplateSpec"]]
"""
A structure suitable for generating ConfigTemplate, e.g.
```
{
  "a" : [ ("minmax",{minv=-1,maxv:+1}), ("isint":{}) ],
  "b" : {
    "b1" : [("isint":{})],
    "b2" : [ ("minmax",{minv=0,maxv:+2}), ("isint":{}) ],
  }
}
```
"""


def check_configuration(template: ConfigTemplate, config: Config) -> None:
    """
    Check that the configuration is valid under the provided template.
    Add errors to ConfigErrors if any of the configuration field is invalid,
      missing or superfluous.
    """

    # if an iterable of methods: applying the checker methods on the value
    # if a ConfigTemplate: a recursive call to this sub configuration dict
    checkers: Iterable[CheckerMethod] | "ConfigTemplate"

    for name, value in config.items():
        try:
            checkers = template[name]
        except KeyError:
            ConfigErrors.add(name=name, message="no such configuration field")
        else:
            # sub configuration dictionary, recursive call
            if isinstance(checkers, dict):
                if isinstance(value, dict):
                    try:
                        check_configuration(checkers, value)
                    except ConfigError as cve:
                        ConfigErrors.append(cve)
                else:
                    ConfigErrors.add(
                        name=name, value=value, message="expected a configuration dict"
                    )
            # "simple" value, checking it is valid
            else:
                checker: CheckerMethod
                for checker in checkers:
                    try:
                        checker(name, value)
                    except ConfigError as cav:
                        ConfigErrors.append(cav)
    for name in template:
        if name not in config:
            ConfigErrors.add(name=name, message="missing configuration value")
