from typing import Optional, Generator, Any


Error = tuple[Optional[str], Optional[Any], Optional[str]]
"""
Error key, value and message
"""


class ConfigError(Exception):
    def __init__(
        self,
        name: Optional[str] = None,
        value: Optional[Any] = None,
        message: Optional[str] = None,
    ) -> None:
        self._errors: list[Error] = []
        self.add(name, value, message)

    def add(
        self,
        name: Optional[str] = None,
        value: Optional[Any] = None,
        message: Optional[str] = None,
    ) -> None:
        if any([f is not None for f in (name, value, message)]):
            self._errors.append((name, message, value))

    def __iter__(self) -> Generator[Error, None, None]:
        for error in self._errors:
            yield error
        return None

    @classmethod
    def has_error(self):
        return len(self._errors) > 0


class ConfigErrors:
    _errors: dict[str, ConfigError] = {}
    _current = ConfigError()
    _key: Optional[str] = None

    def __init__(self, key:str):
        cls = self.__class__
        cls._current = ConfigError()
        cls._key = key
    
    @classmethod
    def add(
        cls,
        name: Optional[str] = None,
        value: Optional[Any] = None,
        message: Optional[str] = None,
    ) -> None:
        cls._current.add(name, value, message)

    @classmethod
    def append(cls, other: ConfigError) -> None:
        for error in other:
            cls.add(*list(error))

    @classmethod
    def has_error(cls):
        return cls._current.hasError()

    @classmethod
    def get(cls)->ConfigError:
        return cls._current
        
    def __enter__(self) -> None:
        pass
        
    def __exit__(self, exc_type, exc_val, _) -> None:
        cls = self.__class__
        if exc_type is not None:
            cls.add(value=str(exc_type), message=str(exc_val))
        if cls._current.has_error() and cls._key:
            cls._errors[cls._key] = cls._current
            raise cls._current
