from pathlib import Path
from collections import Counter
from typing import Any, Type, Optional

Checker = Callable[[Any],Optional[Exception]]

class _Checker:
    def __init__(self,method,kwargs)->None:
        self._method = method
        self._kwargs = kwargs
    def __call__(self, name:str, value: Any)->None:
        return self._method(value,**self._kwargs)

def checker(method):
    def impl(**kwargs)->callable:  
        # args should be empty ! throw
        # exception if not
        return _Checker(method,kwargs)  # callable because __call__
    return impl


def _wrong_type(name: str, value: Any, types: Iterable[Type])->None:
    type_str = ", ".join([str(t) for t in types])
    raise TypeError(
        f"configuration field {name} should be of type {type_str}, "
        f"got {type(value)}"
    )

@checker
def optional(name: str, value: Any)->None:
    if value is None:
        raise ValueError()

@checker
def isint(name: str, value: Any)->None:
    return _wrong_type(name,value,(int,))

@checker
def minmax(name: str, value: Any, vmin=-sys.maxsize, vmax: sys.maxsize)->None:
    if value < vmin:
        raise ValueError()
    if value > vmax:
        raise ValueError()

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
        raise FileNotFoundError(
            f"configuration field {name}: failed to find directory {value}"
        )
    if not value.is_dir():
        raise NotADirectoryError(
            f"configuration field {name}: {value} exists but is not a directory"
        )
    
    
        
# example:

config_fields = {
    'a': (is_directory(create=True), optional()),
    'b': (isint(), minmax(vmin=-1,vmax=1)),
}

class Configuration:

    def __init__(
            self,
            config_fields
    )->None:
        self._config_fields = config_fields

    def check(self, config: dict[str,Any])->None:
        for name, value in config.items():
            checks = self._config_fields[name]
            for check in checks:
                check(name,value)
            
        
