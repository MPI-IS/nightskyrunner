"""
Unit tests of the shared_memory module
"""
import time
from nightskyrunner import shared_memory as sm


def test_set_get():
    """
    Testing simple set/get
    """
    memory = sm.root()
    value = "value"
    m1 = memory.sub("m1")
    item1 = m1.item("item1")
    item1.set(value)
    r = item1.get()
    assert item1.get() == value
    assert memory["m1"]["item1"].get() == value


def test_assert():
    """
    testing the assert function
    """
    memory = sm.root()
    item = memory.item("item")
    item.set({"value":1})
    with sm.access(item) as data:
        data["value"]=2
    assert item.get()["value"] == 2
    assert memory["item"].get()["value"] == 2


def test_thread_safe():
    """
    testing the get and set methods
    of MemoryItem are thread safe
    """
    def long_access(item: sm.MemoryItem):
        with sm.access(item) as data:
            data["value"]=2
            time.sleep(0.2)
    item = sm.root().item("item").set({"value":1})
    t = threading.Thread(target=long_access, args=(item,))
    t.start()
    time.sleep(0.1)
    item.set({"value":3})
    assert item.get()["value"]==3
    t.join()
