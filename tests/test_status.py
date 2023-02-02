"""
Unit tests of the status module
"""

import pytest
from typing import Generator
from nightskyrunner import shared_memory as sm
from nightskyrunner.status import Status, State, Level


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


def test_basic(reset_memory):
    """
    Test the basic functionality of status
    """
    status = Status("test")
    status.state(State.running)
    status.message("message")
    status.value("v1", "1")
    status.value("v2", "2")

    status = Status.retrieve("test")
    d = status.get()

    assert d["name"] == "test"
    assert d["message"] == "message"
    assert d["entries"]["v1"] == "1"
    assert d["entries"]["v2"] == "2"
    assert d["state"] == State.running


def test_sm_saving(reset_memory):
    """
    Test that instances
    of Status are properly updated in the
    shared memory.
    """

    status = Status("test")

    status.value("v", "1")
    assert Status.retrieve("test").get()["entries"]["v"] == "1"

    status.value("v", "2")
    assert Status.retrieve("test").get()["entries"]["v"] == "2"

    status.message("msg1")
    assert Status.retrieve("test").get()["message"] == "msg1"

    status.message("msg2")
    assert Status.retrieve("test").get()["message"] == "msg2"

    status.state(State.running)
    assert Status.retrieve("test").get()["state"] == State.running

    status.state(State.off)
    assert Status.retrieve("test").get()["state"] == State.off


def test_callbacks(reset_memory):
    class Count:
        info = 0
        warning = 0
        error = 0

    def info(name: str, message: str) -> None:
        Count.info += 1

    def warning(name: str, message: str) -> None:
        Count.warning += 1

    state_level: dict[State, Level] = {
        State.running: Level.info,
        State.off: Level.warning,
    }

    Status.set_callback(Level.info, info)
    Status.set_callback(Level.warning, warning)

    status = Status("test", state_level=state_level)

    status.message("m1")
    status.message("m2", level=Level.info)
    status.message("m3", level=Level.info)
    status.message("m4", level=Level.warning)
    status.value("v", "1")
    status.value("v", "2", level=Level.warning)
    status.value("v", "3", level=Level.error)
    status.state(State.running)  # info += 1
    status.state(State.running)
    status.state(State.off)  # warning += 1
    status.state(State.running)  # info += 1

    assert Count.info == 4
    assert Count.warning == 3
    assert Count.error == 0
