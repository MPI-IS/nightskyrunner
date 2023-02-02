from pathlib import Path
from collections import Counter
from typing import Any, Type, Optional

Checker = Callable[[Any],Optional[Exception]]

class ConfigField:

    def __init__(
            self,
            name: str,
            optional: bool = False,
            checkers: Union[Checker,Iterable[Checker]]=[]
    )->None:
        self._name = name
        self._optional = optional
        self._checkers = checkers

    def check(self, value: Any)->dict[str, Exception]:
        r: dict[str,Exception] = {}
        for checker in self._checkers:
            try:
                checker(value)
            except Exception as e:
                r[name] = e
        return r

    def mandatory(self)->bool:
        return not self._optional

# ???
a = ConfigField("a", is_directory(create=True))
    

def _wrong_type(name: str, value: Any, types: Iterable[Type])->None:
    type_str = ", ".join([str(t) for t in types])
    raise TypeError(
        f"configuration field {name} should be of type {type_str}, "
        f"got {type(value)}"
    )
    
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
    
    
        
class ConfigurationChecker:
    def __init__(
            self,
            fields: Iterable[ConfigField]
    )->None:
        names = [f._name for f in fields]
        counter = Counter(names)
        for name,count in counter.items():
            if count>1:
                raise ValueError(
                    f"configuration field {name} "
                    "is defined more than once"
                )
        self._fields: dict[str,ConfigField] = {f._name:f for f in fields}
        self._mandatory: list[str] = [
            name for name,config_field in self._fields.items()
            if config_field.mandatory()
        ]
        
    def check(self, config_values: dict[str,any])->dict[str,Exception]:
        r: dict[str,Exception] = {}
        for name, value in config_values.items():
            try:
                config_field = self._fields[name]
            except KeyError:
                r[name] = NameError(f"not support configuration field: {name}")
            else:
                try:
                    config_field.check(value)
                except Exception as e:
                    r[name]=e
        for name in self._mandatory:
            if not name in config_values.keys():
                r[name] = 
        return r
