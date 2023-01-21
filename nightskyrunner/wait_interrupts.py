import os
from pathlib import Path
from typing import Callable, List

from .config_getter import ConfigGetter
from .status import NoSuchStatusError, State, Status

RunnerWaitInterruptor = Callable[[], bool]
RunnerWaitInterruptors = List[RunnerWaitInterruptor]


class FileChangeInterrupt:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._st: float = self._get()

    def _get(self) -> float:
        return os.stat(str(self._path)).st_mtime

    def __call__(self) -> bool:
        st = self._get()
        r: bool
        if st != self._st:
            r = True
        else:
            r = False
        self._st = st
        return r


class StatusStoppingInterrupt:
    def __init__(self, runner_name: str) -> None:
        self._runner_name = runner_name

    def __call__(self) -> bool:
        state_ = Status.retrieve(self._runner_name)
        if state_ is None:
            return True
        try:
            state = state_.get_state()
        except NoSuchStatusError:
            return False
        if state in (State.stopping,):
            return True
        return False


def get_interrupts(
    runner_name: str, config_getter: ConfigGetter
) -> RunnerWaitInterruptors:
    interrupts: RunnerWaitInterruptors = []
    interrupts.append(StatusStoppingInterrupt(runner_name))
    config_interrupt = config_getter.wait_interrupt()
    if config_interrupt is not None:
        interrupts.append(config_interrupt)
    return interrupts
