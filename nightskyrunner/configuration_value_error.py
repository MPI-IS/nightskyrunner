"""
Module which defines the class 'ConfigurationValueError'
"""

from typing import Optional, Generator

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
