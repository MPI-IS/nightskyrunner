from pathlib import Path
from typing import Any, Type, Optional, Protocol

class ConfigurationValueError(Exception):

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
        for name, value, message in other:
            self._errors[name] = (value, message)

    def __iter__(self)->Generator[tuple[str,Any,str],None,None]:
        for name, (value, message) in self._errors:
            yield (name, value, message)
        return None

    def __str__(self):
        return ", ".join(
            [f"{name} ({value}): {message}" for name,value,message in self]
        )
    

class CheckerMethod(Protocol):
    def __call__(self, name: str, value: Any, **kwargs: Any)->None:
        ...

    
class _Checker:
    def __init__(self,method: CheckerMethod, kwargs)->None:
        self._method = method
        self._kwargs = kwargs
    def __call__(self, name:str, value: Any)->None:
        return self._method(value,**self._kwargs)

    
def checker(method: CheckerMethod):
    def impl(**kwargs)->callable:  
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
    return _wrong_type(name,value,(int,))

@checker
def minmax(name: str, value: Any, vmin=-sys.maxsize, vmax: sys.maxsize)->None:
    if value < vmin:
        raise ConfigurationValueError(name, value, "value should be in [{vmin}, {vmax}]")
    if value > vmax:
        raise ConfigurationValueError(name, value, "value should be in [{vmin}, {vmax}]")

@checker
def is_directory(name: str, value: Any, create: bool=False)->None:
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
