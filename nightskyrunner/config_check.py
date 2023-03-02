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


from typing import Any, Optional, Generator, Iterable, Callable
from .config import Config
from .config_error import ConfigError


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



class _Checker:
    def __init__(self, method: CheckerMethod, kwargs) -> None:
        nb_args = len(
            [
                key for key,value
                in inspect.signature(method).parameters.items()
                if value.default==inspect._empty
            ]
        )
        if nb_args!=2:
            raise ValueError(
                f"the function {method.__name__} does not support the "
                "checker decorator: a configuration checker function must "
                "take two arguments (name and value)"
            )
        self._method = method
        self._kwargs = kwargs

    def __call__(self, name: str, value: Any) -> None:
        # note: this function follows the "CheckerMethod"
        # type
        return self._method(name, value, **self._kwargs)


def checker(method: CheckerMethod):
    """
    Decorator for configuration checker functions.
    Returns a partial function that do not take the name and
    value as argument.

    For example:

    @checker
    def above_threshold(name: str, value: Any, threshold: float=0)->None:
        if value<=threshold:
            raise ConfigurationError(name, value, f"under the threshold ({threshold})")

    # config_check can be used to check the inputs of several values for field1
    config_check = { "field1" : above_threshold(threshold=5) }

    # above_threshold can be called:
    above_threshold(threshold=1.)("field1",1.2)
    """

    def _checker_method(**kwargs) -> CheckerMethod:
        return _Checker(method, kwargs)  # callable because __call__

    return _checker_method


ConfigTemplate = dict[str, Iterable[CheckerMethod] | "ConfigTemplate"]
"""
A template is a dictionary allowing the developer to specify the
criterion a configuration dictionary must apply to be valid.
"""


def check_configuration(template: ConfigTemplate, config: Config) -> None:
    """
    Check that the configuration is valid under the provided template.

    Raises:
      A ConfigValueError is any of the configuration field is invalid,
      missing or superfluous.
    """

    _errors: Optional[ConfigValueError] = None

    def add_error(
        _errors: Optional[ConfigValueError], error: ConfigValueError
    ) -> ConfigValueError:
        if _errors is None:
            _errors = error
        else:
            _errors.add(error)
        return _errors

    # if an iterable of methods: applying the checker methods on the value
    # if a ConfigTemplate: a recursive call to this sub configuration dict
    checkers: Iterable[CheckerMethod] | "ConfigTemplate"

    for name, value in config.items():
        try:
            checkers = template[name]
        except KeyError:
            _errors = add_error(
                _errors,
                ConfigValueError(name, None, "no such configuration field"),
            )
        else:

            # sub configuration dictionary, recursive call
            if isinstance(checkers, dict):
                if isinstance(value, dict):
                    try:
                        check_configuration(checkers, value)
                    except ConfigValueError as cve:
                        _errors = add_error(_errors, cve)
                else:
                    _errors = add_error(
                        _errors,
                        ConfigValueError(name, value, "expected a configuration dict"),
                    )

            # "simple" value, checking it is valid
            else:
                checker: CheckerMethod
                for checker in checkers:
                    try:
                        checker(name, value)
                    except ConfigValueError as cav:
                        _errors = add_error(_errors, cav)

    for name in template:
        if name not in config:
            error = ConfigValueError(name, None, "missing configuration value")
            _errors = add_error(_errors, error)

    if _errors is not None:
        raise _errors
