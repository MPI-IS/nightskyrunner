import multiprocessing
from nightskyrunner.shared_memory import SharedMemory, MultiPDict


def test_multiprocess():
    """
    Test the values stored in the shared memory can be 
    accessed 
    """

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

    assert d["value"] == 100

    

    
