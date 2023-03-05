"""
Module defining ConfigError and ConfigErrors
"""

from typing import Optional, Generator, Any


Error = tuple[Optional[str], Optional[Any], Optional[str]]
"""
Error key, value and message
"""


class ConfigError(Exception):
    """
    Error to be raised when there is an error in the configuration
    provided by the user.
    An instance of ConfigError may contain information related to 
    several error messages. Once an instance has been created, 
    errors can be added to it.

    Args:
      name: arbitrary name (key) of the error
      value: entered by the user, which turned out to be 
        incorrect or not supported
      message: arbitrary error message
    """
    def __init__(
        self,
        name: Optional[str] = None,
        value: Optional[Any] = None,
        message: Optional[str] = None,
    ) -> None:
        self._errors: list[Error] = []
        if any((name, value, message)):
            self.add(name, value, message)

    def add(
        self,
        name: Optional[str] = None,
        value: Optional[Any] = None,
        message: Optional[str] = None,
    ) -> None:
        """
        Adding another message error
        """
        if any([f is not None for f in (name, value, message)]):
            self._errors.append((name, message, value))

    def __iter__(self) -> Generator[Error, None, None]:
        """
        For iterating over all the error messages
        """
        for error in self._errors:
            yield error
        return None

    def has_error(self) -> bool:
        """
        True if any error message has been added
        """
        return len(self._errors) > 0

    def __str__(self) -> str:
        return ", ".join([" | ".join([str(e) for e in error]) for error in self])


class ConfigErrors:
    """
    Class for managing a dictionary of instances of ConfigError.
    Should be used as a context manager:

    ```
    with ConfigErrors("arbitrary_key"):

        try:
          a = read()
        except Exception as e:
          # add an error to the set "arbitrary_key"
          ConfigErrors.add(name="a",message=str(e))

        # getting the current instance of ConfigError
        # (the one related to "arbitrary_key")
        config_error: ConfigError = ConfigErrors.get()

    # the ConfigError corresponding to all the errors
    # related to "arbitrary_key" is raised when exiting
    # the context manager
        
    # getting the instance of ConfigError related
    # to "arbitrary_key"
    config_error = ConfigErrors.errors()["arbitrary_key"]
    ```
    """
    
    _errors: dict[str, ConfigError] = {}
    _current = ConfigError()
    _key: Optional[str] = None

    def __init__(self, key: str)->None:
        cls = self.__class__
        cls._current = ConfigError()
        cls._key = key

    @classmethod
    def clear(cls)->None:
        """
        clear all the stored instances of ConfigError,
        i.e. the get method will return an empty dictionary
        """
        cls._errors = {}
        cls._current = ConfigError()
        cls._key = None

    @classmethod
    def add(
        cls,
        name: Optional[str] = None,
        value: Optional[Any] = None,
        message: Optional[str] = None,
    ) -> None:
        """
        Add a new error to the current instance
        of ConfigError
        """
        cls._current.add(name, value, message)

    @classmethod
    def append(cls, other: ConfigError) -> None:
        """
        Append the error to the current instance
        of ConfigError
        """
        for error in other:
            cls.add(*list(error))

    @classmethod
    def has_error(cls):
        """
        Returns True if the current instance
        of ConfigError has been added at least
        one error
        """
        return cls._current.has_error()

    @classmethod
    def get(cls) -> ConfigError:
        """
        Return the current instance of ConfigError
        """
        return cls._current

    @classmethod
    def errors(cls) -> dict[str, ConfigError]:
        """
        Return all the instances of ConfigError
        (i.e. one per context manager that has
        been instantiated)
        """
        return cls._errors

    def __enter__(self) -> None:
        pass

    def __exit__(self, exc_type, exc_val, _) -> None:
        cls = self.__class__
        if exc_type is not None:
            cls.add(value=str(exc_type), message=str(exc_val))
        if cls._current.has_error() and cls._key:
            cls._errors[cls._key] = cls._current
            raise cls._current
