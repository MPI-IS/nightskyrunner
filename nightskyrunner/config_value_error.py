"""
Module which defines the class 'ConfigValueError'
"""

from typing import Optional, Generator, Protocol

class _AccError(Protocol, Exception):
    def __iter__(self):
        ...

    def add(self, other: type['_AccError'])->None:
        ...

    def len(self)->int:
        ...

class _AccErrorContext:
    def __init__(self, cls: type[_AccError]):
        self._error = cls()
        self._cls = cls

    def add(self, *args, **kwargs) -> None:
        """
        Append another error
        """
        self._error.add(self._cls(*args,**kwargs))
        
    def __enter__(self):
        return self

    def __exit__(self):
        if len(self._error)>0:
            raise self._error
    

def accumulate_error(cls: type[_AccError], method: Callable[[Any],Any]):
    def r(*args, **kwargs):
        with _AccErrorContext(cls) as error:
            error_args = [error]
            error_args.expend(args)
            method(*error_args, kwargs)
    return r
        

class ConfigError(_AccError):

    def __init__(
            self, message:Optional[str]=None
    )->None:
        self._messages: list[str]
        if message:
            self._messages = [message]
        else:
            self._messages = []

    def __iter__(self)->Generator[str,None,None]:
        for message in self._messages:
            yield message
        return None
            
    def add(self, other: 'ConfigError')->None:
        for message in other:
            self._messages.append(message)

    def len(self)->int:
        return len(self._messages)

    def __str__(self):
        return ", ".join(self._messages)
    

class config_error(_AccErrorContext):
    def __init__(self):
        super().__init__(self,ConfigError)

    
class ConfigValueError(Exception):
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

    def add(self, other: "ConfigValueError") -> None:
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

class config_value_error(_AccErrorContext):
    def __init__(self):
        super().__init__(self,ConfigValueError)

