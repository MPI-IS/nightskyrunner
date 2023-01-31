"""
Unit tests of the shared_memory module
"""

import pytest
import time
import threading
from typing import Generator
from nightskyrunner import shared_memory as sm


@pytest.fixture
def reset_memory(
    request,
    scope="function",
) -> Generator[None, None, None]:
    """
    clear shared memory on exit
    """
    yield None
    sm.clear()


def test_set_get(reset_memory):
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


def test_assert(reset_memory):
    """
    testing the assert function
    """
    memory = sm.root()
    item = memory.item("item")
    item.set({"value": 1})
    with sm.access(item) as data:
        data["value"] = 2
    assert item.get()["value"] == 2
    assert memory["item"].get()["value"] == 2


def test_thread_safe(reset_memory):
    """
    testing the get and set methods
    of MemoryItem are thread safe
    """

    def long_access(item: sm.MemoryItem):
        with sm.access(item) as data:
            data["value"] = 2
            time.sleep(0.2)

    item = sm.root().item("item")
    item.set({"value": 1})
    t = threading.Thread(target=long_access, args=(item,))
    t.start()
    time.sleep(0.1)
    item.set({"value": 3})
    assert item.get()["value"] == 3
    t.join()


def test_raise_if_exists(reset_memory):
    """
    Testing if a ValueError is raised
    when creating an already existing item
    """
    sm.root().item("item")
    sm.root().item("item", exists_ok=True)
    with pytest.raises(ValueError):
        sm.root().item("item", exists_ok=False)

    sm.root().sub("sub")
    sm.root().sub("sub", exists_ok=True)
    with pytest.raises(ValueError):
        sm.root().sub("sub", exists_ok=False)
