"""
Tests of the status module
"""

from typing import Any, Dict, Generator

import pytest
from typing_extensions import TypedDict

from nightskyrunner.shared_memory import SharedMemory
from nightskyrunner.status import Level, NoSuchStatusError, State, Status


@pytest.fixture
def reset_memory(
    request,
    scope="function",
) -> Generator[None, None, None]:
    """
    clear shared memory on exit
    """
    yield None
    SharedMemory.clear()


class _StatusTestDict(TypedDict):
    v1: str
    v2: str


def test_basic(reset_memory):
    """
    Test the basic functionality of status,
    i.e. the API can set values to the
    attributes of an instance of Status,
    and the dictionary returned by this
    instances has matching values.
    """
    status = Status("test", "test")
    status.state(State.running)
    status.entries(_StatusTestDict(v1="1", v2="2"))

    status = Status.retrieve("test")
    d = status.get()

    assert d["name"] == "test"
    assert d["entries"]["v1"] == "1"
    assert d["entries"]["v2"] == "2"
    assert d["state"] == State.running.name


def test_sm_saving(reset_memory):
    """
    Test that instances
    of Status are properly updated in the
    shared memory.
    """

    status = Status("test", "test")

    # the value function of status should write the instance
    # of status in the shared memory
    status.entries(_StatusTestDict(v1="1", v2="2"))
    # checking this is indeed the case.
    assert Status.retrieve("test").get()["entries"]["v1"] == "1"
    assert Status.retrieve("test").get()["entries"]["v2"] == "2"

    status.state(State.running)
    assert Status.retrieve("test").get()["state"] == State.running.name

    status.state(State.off)
    assert Status.retrieve("test").get()["state"] == State.off.name


def test_retrieve_error(reset_memory):
    """
    Testing retrieving an non existing status
    raises an exception
    """
    with pytest.raises(NoSuchStatusError):
        Status.retrieve("not_existing")


def test_delete(reset_memory):
    """
    Testing the delete function
    (deleting an instance of Status from
    the shared memory)
    """
    status_delete = Status("test_delete", "test")
    status_delete.message = "delete"

    status_keep = Status("test_keep", "test")
    status_keep.message = "keep"

    assert len(Status.retrieve_all()) == 2

    Status.delete("test_delete")

    assert len(Status.retrieve_all()) == 1


def test_clear_all(reset_memory):
    """
    Testing the status clear_all method
    (deleting all instances of Status
    from the shared memory)
    """
    status_delete = Status("test_delete", "test")
    status_delete.message = "delete"

    status_keep = Status("test_keep", "test")
    status_keep.message = "keep"

    assert len(Status.retrieve_all()) == 2

    Status.clear_all()

    assert len(Status.retrieve_all()) == 0


def test_error(reset_memory):
    """
    When the state of an instance of Status is
    switched to "error" or "issue", the dictionary
    returned by the status get method should give
    both this information. Once state is switched
    back to something else, the dictionary should
    contains the last encountered error/issue messages.
    """
    status = Status("test_error", "test")
    status.state(State.running)
    # state is switched to error.
    status.state(State.error, error="error message")
    # checking the dictionary says so
    d = status.get()
    assert d["error"]["message"] == "error message"
    # state is back to running
    status.state(State.running)
    d = status.get()
    assert "message" not in d["error"].keys()
    # but keeping in memory the last error
    # encountered
    assert d["error"]["previous"] == "error message"
    status.state(State.error, error="error message 2")
    d = status.get()
    assert d["error"]["message"] == "error message 2"
    assert d["error"]["previous"] == "error message"


def test_issue(reset_memory):
    status = Status("test_issue", "test")
    status.state(State.running)
    d = status.get()
    status.set_issue("issue message")
    d = status.get()
    assert d["issue"]["message"] == "issue message"
    status.remove_issue()
    d = status.get()
    assert "message" not in d["issue"].keys()
    assert d["issue"]["previous"] == "issue message"
    status.set_issue("issue message 2")
    d = status.get()
    assert d["issue"]["message"] == "issue message 2"
    assert d["issue"]["previous"] == "issue message"
    status.remove_issue()
    d = status.get()
    assert "message" not in d["issue"].keys()
    assert d["issue"]["previous"] == "issue message 2"
