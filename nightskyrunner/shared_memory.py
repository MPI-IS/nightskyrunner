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
from typing import Any, Optional, Type, cast, TypeVar, Union


def _do_lock(method):
    @wraps(method)
    def _impl(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)

    return _impl


class MemoryItem:
    """
    Thread safe element of a shared memory.
    Can host arbitrary data.
    """

    _upload_queues: list[Queue] = []
    
    def __init__(self, key_path: list[str]=[]) -> None:
        self._lock = threading.Lock()
        self._data: Optional[Any] = None
        self._key_path = key_path
        
    @_do_lock
    def get(self) -> Optional[Any]:
        """
        Returns a deep copy of the data
        """
        r = copy.deepcopy(self._data)
        return r

    @_do_lock
    def set(self, data) -> None:
        """
        Set the data
        """
        self._data = copy.deepcopy(data)
        
            
class access:
    """
    Context manager for accessing in a thread safe manner
    the data of an instance of MemoryItem.

    Args:
      An instance of memory item which data is mutable
    """

    def __init__(self, memory_item: MemoryItem) -> None:
        self._memory_item = memory_item
        self._data = memory_item._data
        self._lock = memory_item._lock

    def __enter__(self) -> Optional[Any]:
        self._lock.acquire()
        return self._data

    def __exit__(self, _, __, ___) -> None:
        self._lock.release()


# for the the SharedMemory._new method to support both
# MemoryItem and SharedMemory as argument / return type
_Element = TypeVar("_Element", MemoryItem, "SharedMemory")


class SharedMemory:
    """
    Thread safe dictionary which keys are strings and elements
    are instances of MemoryItem and instances of SharedMemory.
    """

    def __init__(self) -> None:
        self._d: dict[str, MemoryItem | "SharedMemory"] = {}
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
            return item

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

    def __getitem__(self, key: str) -> Union["SharedMemory", MemoryItem]:
        """
        Returns the instance stored under the key.

        Raises:
          KeyError if no instance under this key.
        """
        with self._lock:
            return self._d[key]

    def get_memory(self, key: str) -> "SharedMemory":
        """
        Returns the instance of SharedMemory stored under the key.

        Raises:
          KeyError if no instance under this key.
          ValueError if the key maps to an instance of MemoryItem.
        """
        v = self._d[key]
        if isinstance(v, MemoryItem):
            raise ValueError(
                f"the key {key} is not mapped to a sub-shared memory, "
                "but to an instance of MemoryItem"
            )
        return v

    def get_item(self, key: str) -> MemoryItem:
        """
        Returns the instance of Memory stored under the key.

        Raises:
          KeyError if no instance under this key.
          ValueError if the key maps to an instance of SharedMemory.
        """
        v = self._d[key]
        if not isinstance(v, MemoryItem):
            raise ValueError(
                f"the key {key} is not mapped to an instance of MemoryItem, "
                "but to an instance of SharedMemory"
            )
        return v


_memory = SharedMemory()

class MirroringQueue:

    def __init__(
            self, upload_queue: Queue, download_queue: Queue
    ):
        self._upload_queue = upload_queue
        self._download_queue = download_queue
        self._running = False
        self._thread: Optional[Thread] = None

    def run(self):
        self._running = True
        sm = shared_memory.root()
        while running.value:
            value, keys_path = self._download_queue.get()
            item: SharedMemory | MemoryItem = sm
            l = len(keys_path)
            for index, key in enumerate(keys_path):
                if index<l-1:
                    item = item.sub(key, exists_ok=True)
                else:
                    item = item.item(key, exists_ok=True)
            item.set(value)
        
    def start(self):
        self._thread = Thread(target=self.run)
        self._tread.start()

    def stop(self):
        if self._thread is None:
            return
        self._running = False
        self._thread.join()
        self._thread = None
        
mirroring_queues: list[MirroringQueue] = []


def mirroring_queues()->tuple[Queue,Queue]:
    upload_queue = Queue()
    download_queue = Queue()
    _upload_queues.append(in_queue)
    _download_queues.append(out_queue)

    def _sm_sync(
            sm: SharedMemory,
            queue: multiprocessing.Queue,
            running: multiprocessing.Value
    )->None:

    


def root() -> SharedMemory:
    """
    Returns the global shared memory.
    """
    global _memory
    return _memory


def clear() -> None:
    """
    clear the global shared memory
    """
    global _memory
    _memory = SharedMemory()


    
    
