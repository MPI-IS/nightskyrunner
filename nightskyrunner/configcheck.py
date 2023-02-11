"""
Module implementing code for checking if a configuration dictionary is valid under rules
specified by the developer.

Developers can create a template expressing the rules a configuration dictionary must
enforce to be valid, e.g.

``` python
    @checker
    def is_above(name: str, value: Any, threshold=1.0)->None:
        if value<threshold:
            raise ConfigurationValueError(name, value, f"under the threshold {threshold}")

    @checker is_float(name: str, value: float)->None:
        if not isinstance(float, value):
            raise ConfigurationValueError(name, value, f"value must be a float")

    template = {
        "field1": (is_float(), is_above(threshold=2.)),
        "field2": (is_float(),)
    }

    config_ok = {
        "field1": 3.0,
        "field2": 1.3
    }
    check_configuration(template, config_ok)

    # raises a ConfigurationValueError:
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

class ConfigurationValueError(Exception):
    """
    To be raised when the user provided an incorrect input(s) for
    configuration field(s).

    Once an instance has been created, it is possible to add to it
    other instances. Once can then iterate over the errors:

    ```python
    error = ConfigurationError("threshold", -1.1, "value must be positive")
    error.add(ConfigurationError("threshold", -1.1, "value must be an integer")

    for name, value, message:
        print(f"field {name}: unsupported value {value}: {message}")

    # prints:
    # field threshold: unsupported value -1.1: value must be positive
    # field threshold: unsupported value -1.1: value must be an integer
    ```

    Args:
      name: name of the field
      value: the value entered by the user
      message: why this value is not suitable
    """

    def __init__(
        self,
        name: Optional[str] = None,
        value: Optional[Any] = None,
        message: Optional[str] = None,
    ) -> None:
        self._errors: dict[str, tuple[Optional[Any], Optional[str]]] = {}
        if name is not None:
            self._errors[name] = (value, message)

    def __len__(self) -> int:
        return len(self._errors)

    def add(self, other: "ConfigurationValueError") -> None:
        """
        Append another error
        """
        for name, value, message in other:
            self._errors[name] = (value, message)

    def __iter__(
        self,
    ) -> Generator[tuple[str, Optional[Any], Optional[str]], None, None]:
        """
        Generator for iterating over the errors.

        Yields:
            Tuple: name of the field, user entered value,
              why this value can not be accepted
        """
        name: str
        value: Optional[Any]
        message: Optional[str]
        for name, (value, message) in self._errors.items():
            yield (name, value, message)
        return None

    def __str__(self):
        return ", ".join(
            [f"{name} ({value}): {message}" for name, value, message in self]
        )


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

    def impl(**kwargs) -> CheckerMethod:
        return _Checker(method, kwargs)  # callable because __call__

    return impl


ConfigTemplate = dict[str, Iterable[CheckerMethod]]
"""
A template is a dictionary allowing the developer to specify the 
criterion a configuration dictionary must apply to be valid.
"""

def check_configuration(
    template: ConfigTemplate,
    config: Config,
) -> None:
    """
    Check that the configuration is valid under the provided template.

    Raises:
      A ConfigurationValueError is any of the configuration field is invalid,
      missing or superfluous.
    """

    _errors: Optional[ConfigurationValueError] = None

    def add_error(
        _errors: Optional[ConfigurationValueError], error: ConfigurationValueError
    ) -> ConfigurationValueError:
        if _errors is None:
            _errors = error
        else:
            _errors.add(error)
        return _errors

    for name, value in config.items():
        try:
            checkers = template[name]
        except KeyError:
            _errors = add_error(
                _errors,
                ConfigurationValueError(name, None, "no such configuration field"),
            )
        else:
            checker: CheckerMethod
            for checker in checkers:
                try:
                    checker(name, value)
                except ConfigurationValueError as cav:
                    _errors = add_error(_errors, cav)

    for name in template:
        if name not in config:
            error = ConfigurationValueError(name, None, "missing configuration value")
            _errors = add_error(_errors, error)

    if _errors is not None:
        raise _errors
