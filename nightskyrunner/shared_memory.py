"""
Methods for accessing a global dictionary in a thread safe manner.

Examples:

 ```python
 from nightskyrunner import shared_memory as sm

 # getting the global shared memory
 memory = sm.root()

 # create a "sub" shared memory
 shared = memory.sub("shared")

 # create a memory item
 item = shared.item("item")

 # set arbitrary data to items
 item.set("I am item")

 # retrieving item
 item = memory["shared"]["item"]

 # getting a (deep) copy of item's data
 s = item.get()

 # overwriting item's data
 item.set("I am item, indeed")

 # getting item's data in mutable form
 with sm.access(item) as data:
     data = "I confirm I am item"
 ```

"""

import copy
import threading
from functools import wraps
from typing import Any, Optional, Type, cast, TypeVar


def _do_lock(method):
    @wraps(method)
    def _impl(self):
        with self._lock:
            method(self)

    return _impl


class MemoryItem:
    """
    Thread safe element of a shared memory.
    Can host arbitrary data.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._data: Optional[Any] = None

    @_do_lock
    def get(self) -> Optional[Any]:
        """
        Returns a deep copy of the data
        """
        return copy.deepcopy(self._data)

    @_do_lock
    def set(self, data) -> None:
        """
        Set the data
        """
        self._data = copy.deepcopy(data)


class access:
    """
    Context manager for accessing in a thread safe manner
    the (mutable) data of an instance of MemoryItem.
    """

    def __init__(self, memory_item: MemoryItem) -> None:
        self._data = memory_item._data
        self._lock = memory_item._lock

    def __enter__(self) -> Optional[Any]:
        self._lock.acquire()
        return self._data

    def __exit__(self, _, __, ___) -> None:
        self._lock.release()


_Element = TypeVar("_Element", MemoryItem, "SharedMemory")


class SharedMemory:
    """
    Thread safe dictionary which keys are strings and elements
    are instances of MemoryItem and instances of SharedMemory.
    """

    def __init__(self) -> None:
        self._d: dict[str, MemoryItem | "SharedMemory"]
        self._lock = threading.Lock()

    def _new(
        self,
        key: str,
        target_type: Type[_Element],
        exists_ok: bool,
    ) -> _Element:

        with self._lock:
            try:
                item = self._d[key]
            except KeyError:
                r = target_type()
                self._d[key] = r
                return r
            if not isinstance(item, target_type):
                raise ValueError(
                    f"key {key} already exists and does not refer to an instance of "
                    f"a {target_type.__name__} (refers to an instance of {item.__class__.__name__})"
                )
            if not exists_ok:
                raise ValueError(f"'sub' shared memory at key {key} " "already exists")
            return r

    def sub(self, key: str, exists_ok: bool = False) -> "SharedMemory":
        """
        Creates and return a new instance of SharedMemory

        Args:
         key: 'dictionary' key under which the new shared memory will be stored
         exists_ok: if True, will not throw an exception if an instance of SharedMemory
           already exists under this key

        Returns:
          An instance of SharedMemory

        Raises:
          ValueError if there is already an instance under this key and exists_ok is False;
          or exists_ok is True but this existing instance is of MemoryItem
        """
        return self._new(key, cast(Type["SharedMemory"], self.__class__), exists_ok)

    def item(self, key: str, exists_ok: bool = False) -> MemoryItem:
        """
        Creates and return a new instance of MemoryItem

        Args:
         key: 'dictionary' key under which the new shared memory will be stored
         exists_ok: if True, will not throw an exception if an instance of MemoryItem
           already exists under this key

        Returns:
          An instance of MemoryItem

        Raises:
          ValueError if there is already an instance under this key and exists_ok is False;
          or exists_ok is True but this existing instance is of SharedMemory
        """
        return self._new(key, cast(Type[MemoryItem], MemoryItem), exists_ok)

    def __getitem__(self, key: str) -> "SharedMemory" | MemoryItem:
        """
        Returns the instance stored under the key.

        Raises:
          KeyError if no instance under this key.
        """
        with self._lock:
            if key not in self._d:
                raise KeyError(key)
            return self._d[key]


_memory = SharedMemory()


def root() -> SharedMemory:
    """
    Returns the global shared memory.
    """
    global _memory
    return _memory
