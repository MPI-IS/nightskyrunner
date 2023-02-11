from pathlib import Path
from typing import Any, Type, Optional, Protocol, Generator, Iterable, Callable

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
            name: Optional[str]=None,
            value: Optional[Any]=None,
            message: Optional[str]=None
    )->None:
        self._errors: dict[str,tuple[Optional[Any],Optional[str]]] = {}
        if name is not None:
            self._errors[name] = (value, message)

    def add(self, other: "ConfigurationValueError")->None:
        """
        Append another error
        """
        for name, value, message in other:
            self._errors[name] = (value, message)

    def __iter__(self)->Generator[tuple[str,Optional[Any],Optional[str]],None,None]:
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
            [f"{name} ({value}): {message}" for name,value,message in self]
        )
    

class CheckerMethod(Protocol):
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
    def __call__(self, name: str, value: Any, **kwargs: Any)->None:
        ...

    
class _Checker:
    def __init__(self,method: CheckerMethod, kwargs)->None:
        self._method = method
        self._kwargs = kwargs
    def __call__(self, name:str, value: Any)->None:
        return self._method(value,**self._kwargs)

    
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
    """
    def impl(**kwargs)->Callable:
        return _Checker(method,kwargs)  # callable because __call__
    return impl


def _wrong_type(name: str, value: Any, types: Iterable[Type])->None:
    type_str = ", ".join([str(t) for t in types])
    raise ConfigurationValueError(name, value, f"wrong type (got {type(value)}, expect {type_str})")

@checker
def optional(name: str, value: Any)->None:
    if value is None:
        raise ConfigurationValueError(name, value, "configuration missing (required)")

@checker
def isint(name: str, value: Any)->None:
    """
    Raises a ConfigurationError is value is not an integer.
    """
    return _wrong_type(name,value,(int,))

@checker
def minmax(name: str, value: Any, vmin=-sys.maxsize, vmax= sys.maxsize)->None:
    """
    Raises a ConfigurationError if value is not in the internval vmin, vmax.
    """
    if value < vmin:
        raise ConfigurationValueError(name, value, "value should be in [{vmin}, {vmax}]")
    if value > vmax:
        raise ConfigurationValueError(name, value, "value should be in [{vmin}, {vmax}]")

@checker
def is_directory(name: str, value: Any, create: bool=False)->None:
    """"
    Raises a ConfigurationError if value is not a directory.
    If create is True, this method will attempt to create the directory
    if it does not exists.
    """
    if isinstance(value,str):
        value = Path(value)
    if not isinstance(value,Path):
        _wrong_type(name, value, (str,Type[Path]))
    if not value.exists():
        if create:
            value.mkdirs(parent=True)
            return
        raise ConfigurationValueError(name, value, "directory not found")
    if not value.is_dir():
        raise ConfigurationValueError(name, value, "not a directory")
