from typing import Optional
import multiprocessing as mp
from multiprocessing import managers, sharedctypes
from threading import Lock

MultiPDict = managers.DictProxy
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

    ```
    def process(memories: dict[str, MultiPDict]):
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
    _memories: dict[str, MultiPDict] = {}
    _lock = Lock()

    @classmethod
    def get(cls, memory_key: str) -> MultiPDict:
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
    def set(cls, memory_key: str, memory: MultiPDict) -> None:
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
    def get_all(cls) -> dict[str, MultiPDict]:
        """
        Return all dictionaries
        """
        return cls._memories

    @classmethod
    def set_all(cls, memories: dict[str, MultiPDict]) -> None:
        """
        Overwrite all dictionaries.
        """
        cls._memories = memories
