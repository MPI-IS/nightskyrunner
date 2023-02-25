
from typing import Optional, Generator


Error = list[tuple[Optional[str], Optional[Any], Optional[str]]]

class ConfigError(Exception):

    def __init__(self)->None:
        self._errors: Error = []

    def add(
            self,
            name:Optional[str]=None,
            value:Optional[Any]=None,
            message: Optional[str]=None
    ) -> None:
        self._errors.append(name,message,value)

    def __iter__(self)->Generator[Error, None, None]:
        for error in self._errors:
            yield error
        return None
        
    @classmethod
    def hasError(self):
        return len(self._errors)>0

    
class ConfigErrors:
    _errors: Dict[str,ConfigError]={}
    _current = ConfigError()
    _key: Optional[str]=None
    
    @classmethod
    def add(
            cls,
            name:Optional[str]=None,
            value:Optional[Any]=None,
            message: Optional[str]=None
    ) -> None:
        cls._current.add((name,value,message))

    @classmethod
    def has_error(cls):
        return cls._current.hasError()
        
    def __enter__(self, key:str)->None:
        cls._current = ConfigError()
        cls._key = key
    
    def __exit__(self, exc_type, exc_val, _)->None:
        c = self.__class__
        if exc_type is not None:
            c.add(value=str(exc_type),message=str(exc_val))
        if c._current.has_error():
            c._errors[c._key]=cls._current
            raise cls._current
    
    
            


