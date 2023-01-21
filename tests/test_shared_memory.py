import multiprocessing
from typing import Dict

from nightskyrunner.shared_memory import DictProxy, SharedMemory


def test_multiprocess():
    """
    Test the values stored in the shared memory can be
    accessed
    """

    def process(memories: Dict[str, DictProxy]):
        SharedMemory.set_all(memories)
        d = SharedMemory.get("d")
        d["value"] = 100

    d = SharedMemory.get("d")
    d["value"] = 0

    p = multiprocessing.Process(target=process, args=(SharedMemory.get_all(),))
    p.start()
    p.join()

    assert d["value"] == 100
