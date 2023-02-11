from typing import Any, Optional, Generator, Iterable, Callable


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


Config = dict[str, Any]
ConfigTemplate = dict[str, Iterable[CheckerMethod]]


def check_configuration(
    template: ConfigTemplate,
    config: Config,
) -> None:

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
