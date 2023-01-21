"""
Module defining the SharedMemory class.
"""

import multiprocessing as mp
from contextlib import contextmanager
from multiprocessing import managers, sharedctypes
from threading import Lock
from typing import Dict, Generator, Optional

DictProxy = managers.DictProxy
""" Dict proxy, i.e. shared memory dictionary """

MultiPDict = Dict[str, DictProxy]
""" multiprocessing dict"""

Manager = managers.SyncManager
""" multiprocessing manager """

MpValue = sharedctypes.SynchronizedBase
""" multiprocessing shareable value """


class SharedMemory:
    """
    For sharing data accross threads and processes.
    Maintain a dictionary which keys are arbitrary strings
    and values multiprocessing dictionaries.

    To share these dictionaries with a new process, they need
    to be passed as argument to the target function of the process,
    and the function should set them to its local SharedMemory class:

    ```python
    def process(memories: Dict[str, MultiPDict]):
        SharedMemory.set_all(memories)
        d = SharedMemory.get("d")
        d["value"]=100

    d = SharedMemory.get("d")
    d["value"]=0

    p = multiprocessing.Process(
        target=process, args=(SharedMemory.get_all(),)
    )
    p.start()
    p.join()

    # assert d["value"] == 100
    ```

    Limitation: only the dictionaries already created when the process is spawned
    will be shared (no such limitations for threads)

    Because the dictionary are multiprocess dictionary, the
    values they hold must be pickable.
    """

    _manager: Optional[Manager] = None
    _memories: Dict[str, DictProxy] = {}
    _lock = Lock()

    @classmethod
    def get(cls, memory_key: str) -> DictProxy:
        """
        Getting the dictionary associated with the key,
        creating it if necessary.
        """
        with cls._lock:
            if cls._manager is None:
                cls._manager = mp.Manager()
            try:
                return cls._memories[memory_key]
            except KeyError:
                m = cls._manager.dict()
                cls._memories[memory_key] = m
            return m

    @classmethod
    def set(cls, memory_key: str, memory: DictProxy) -> None:
        """
        Set a dictionary associated to the key, overwriting the current
        dictionary if any
        """
        with cls._lock:
            if cls._manager is None:
                cls._manager = mp.Manager()
            cls._memories[memory_key] = memory

    @classmethod
    def clear(cls, memory_key: Optional[str] = None) -> None:
        """
        Remove the dictionary associated with the key.
        Warning: only for the current process.
        """
        with cls._lock:
            if memory_key is not None:
                del cls._memories[memory_key]
            else:
                cls._memories = {}

    @classmethod
    def get_all(cls) -> Dict[str, DictProxy]:
        """
        Return all dictionaries
        """
        return cls._memories

    @classmethod
    def set_all(cls, memories: Dict[str, DictProxy]) -> None:
        """
        Overwrite all dictionaries.
        """
        cls._memories = memories

    @classmethod
    def stop(cls) -> None:
        """
        Stops the manager and frees all resources, including sockets.
        """
        with cls._lock:
            if cls._manager:
                cls._memories.clear()
                cls._manager.shutdown()
                cls._manager = None


@contextmanager
def clean_shared_memory() -> Generator[None, None, None]:
    """
    Context manager for cleaning the shared memory, including
    the release of sockets.
    """
    try:
        yield
    finally:
        SharedMemory.stop()
