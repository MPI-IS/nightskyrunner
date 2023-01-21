from typing import Any, Dict, List, Optional

from .config_getter import ConfigGetter
from .runner import (ProcessRunner, RunnerWaitInterruptors, ThreadRunner,
                     status_error)
from .shared_memory import SharedMemory
from .status import Level, Status, StatusDict


@status_error
class TestProcessRunner(ProcessRunner):
    shared_memory_key: str = "test_process_runner"

    def __init__(
        self,
        name: str,
        config_getter: ConfigGetter,
        interrupts: RunnerWaitInterruptors = [],
        core_frequency: float = 100.0,
    ) -> None:
        super().__init__(
            name,
            config_getter,
            interrupts=interrupts,
            core_frequency=core_frequency,
        )
        self._value: Optional[int] = None
        # this will create the shared memory.
        # It is important to create the shared memory
        # in the init method to make sure the shared
        # memory will be accessible to other runners.
        memory = SharedMemory.get(self.shared_memory_key)
        memory["field"] = 0

    def on_exit(self) -> None:
        goodbye = self._config_getter.get()["goodbye"]
        self.log(Level.info, goodbye)

    def iterate(self):
        value = int(self._config_getter.get()["field"])
        if value != self._value:
            self._value = value
            self.log(Level.info, f"new field value: {value}")
            memory = SharedMemory.get(self.shared_memory_key)
            memory["field"] = value
        self.log(Level.debug, f"{self.name} iterating")


@status_error
class TestThreadRunner(ThreadRunner):
    def __init__(
        self,
        name: str,
        config_getter: ConfigGetter,
        interrupts: RunnerWaitInterruptors = [],
        core_frequency: float = 100.0,
    ) -> None:
        super().__init__(
            name,
            config_getter,
            interrupts=interrupts,
            core_frequency=core_frequency,
        )
        self._value: Optional[int] = None
        self._sm_value: Optional[int] = None

    def on_exit(self) -> None:
        goodbye = self._config_getter.get()["goodbye"]
        self.log(Level.info, goodbye)

    def iterate(self):
        value = int(self._config_getter.get()["field"])
        if value != self._value:
            self._value = value
            self.log(Level.info, f"new field value: {value}")
        memory = SharedMemory.get(TestProcessRunner.shared_memory_key)
        try:
            sm_value = int(memory["field"])
        except KeyError:
            sm_value = None
        if sm_value != self._sm_value:
            self._sm_value = sm_value
            self.log(Level.info, f"new shared memory field value: {sm_value}")
        self.log(Level.debug, f"{self.name} iterating")


@status_error
class TestStatusRunner(ThreadRunner):
    def __init__(
        self,
        name: str,
        config_getter: ConfigGetter,
        interrupts: RunnerWaitInterruptors = [],
        core_frequency: float = 100.0,
    ) -> None:
        super().__init__(
            name,
            config_getter,
            interrupts=interrupts,
            core_frequency=core_frequency,
        )

    def iterate(self) -> None:
        all_status: List[Status] = Status.retrieve_all()
        for status in all_status:
            status_dict: StatusDict = status.get()
            summary = ", ".join(
                [
                    f"{key}: {repr(value)}"
                    for key, value in status_dict.items()
                    if value
                ]
            )
            self.log(Level.info, summary)
