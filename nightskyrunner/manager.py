"""
Module defining ManagerConfigGetter, FixedRunners and Manager.
"""

import logging
import time
from threading import Thread
from typing import Dict, Iterable, List, Optional, Tuple

from .config import Config
from .error_info import get_error_info
from .factories import RunnerFactory
from .runner import Runner, RunnerWaitInterruptors
from .shared_memory import SharedMemory
from .status import State, Status


class ManagerConfigGetter:
    """
    Abstract superclass for factories of [factories.RunnerFactory]().
    A [factories.RunnerFactory]() is a factory which instantiate [runner.Runner]().
    A ManagerConfigGetter is therefore a factory of factories.
    """

    def __init__(self) -> None:
        # nothing to do
        ...

    def get(self) -> Tuple[RunnerFactory, ...]:
        raise NotImplementedError()


class FixedRunners(ManagerConfigGetter):
    """
    Concrete subclass of [ManagerConfigGetter]() which simply returns
    the instances of [factories.RunnerFactory]() passed as arguments.
    """

    def __init__(self, runner_configs: Tuple[RunnerFactory, ...]) -> None:
        self._runner_configs = runner_configs

    def get(self) -> Tuple[RunnerFactory, ...]:
        return self._runner_configs


def _stop_runners(
    runners: Dict[RunnerFactory, Runner],
    runner_factories: Dict[str, RunnerFactory],
    logger: logging.Logger,
) -> None:
    # stopping the runner that should no longer be
    # running because ...
    for factory, runner in runners.items():
        # ... the runner is no longer listed
        if runner.name not in [name for name in runner_factories.keys()]:
            logger.info(
                f"\tstopping runner {runner.name} (as requested by the current manager configuration)"
            )
            runner.stop(blocking=False)
        # ... the configuration of the runner changed
        elif not factory.same(runner_factories[factory.name]):
            logger.info(
                f"\tstopping runner {runner.name} (because of a change in its manager configuration)"
            )
            runner.stop(blocking=False)


def _start_runners(
    runners: Dict[RunnerFactory, Runner],
    runner_factories: Dict[str, RunnerFactory],
    logger: logging.Logger,
    core_frequency: float = 50.0,
    override: Optional[Config] = None,
) -> None:
    missing_runners = [
        runner
        for runner in runner_factories.keys()
        if runner not in [r.name for r in runners.values()]
    ]
    _runners: List[Runner] = []
    for name, factory in [
        (rf.name, rf)
        for name, rf in runner_factories.items()
        if name in missing_runners
    ]:
        logger.info(f"\tstarting runner {name}")
        runner = factory.instantiate(core_frequency, override)
        runners[factory] = runner
        _runners.append(runner)
    for runner in _runners:
        runner.start()


def _cleanup_runners(
    runners: Dict[RunnerFactory, Runner],
    runner_factories: Dict[str, RunnerFactory],
    logger: logging.Logger,
) -> None:
    to_delete: List[RunnerFactory] = []
    for factory, runner in runners.items():
        if runner.stopped() and runner.name not in runner_factories.keys():
            logger.debug(f"\tcalling exit function of {runner.name}")
            runner.on_exit()
            to_delete.append(factory)
    for factory in to_delete:
        del runners[factory]


def _revive_runners(
    runners: Dict[RunnerFactory, Runner],
    runner_factories: Dict[str, RunnerFactory],
    logger: logging.Logger,
) -> None:
    for factory, runner in runners.items():
        if runner.name in runner_factories.keys() and factory.same(
            runner_factories[runner.name]
        ):
            if not runner.alive():
                logger.info(f"\treviving {runner.name}")
                runner.revive()


def _update_runners(
    runners: Dict[RunnerFactory, Runner],
    config_getter: ManagerConfigGetter,
    logger: logging.Logger,
) -> None:
    # runners are the runners currently running
    # config_getter provides the list of
    # runners that should be running now.
    # This method stops/starts runners accordingly

    desired_runners_: Tuple[RunnerFactory, ...] = config_getter.get()
    desired_runners: Dict[str, RunnerFactory] = {
        rf.name: rf for rf in desired_runners_
    }

    _cleanup_runners(runners, desired_runners, logger)
    _start_runners(runners, desired_runners, logger)
    _stop_runners(runners, desired_runners, logger)
    _revive_runners(runners, desired_runners, logger)


def _stop_runners_batch(
    runners: Iterable[Runner],
    status: Status,
    logger: logging.Logger,
    timeout: float = 60.0,
    warning_every: float = 5.0,
) -> None:
    for runner in runners:
        logger.info(f"\trequesting runner {runner.name} to stop")
        runner.stop(blocking=False)
    start = time.time()
    on_exit_called = {runner.name: False for runner in runners}
    last_warning = time.time()
    while time.time() - start < timeout:
        all_stopped = True
        if time.time() - last_warning > warning_every:
            warn_still_running = True
            last_warning = time.time()
        else:
            warn_still_running = False
        for runner in runners:
            if not runner.stopped():
                all_stopped = False
                if warn_still_running:
                    logger.warning(f"\twaiting for {runner.name} to stop")
            else:
                if not on_exit_called[runner.name]:
                    logger.info(f"\trunner {runner.name}: on exit")
                    runner.on_exit()
                    on_exit_called[runner.name] = True
        if all_stopped:
            logger.info("\tall runners stopped")
            return
    logger.error(
        str(
            f"\texiting because of timeout ({timeout}). "
            f"Did not exit properly: {', '.join([r.name for r in runners if not r.stopped()])}"
        )
    )


def _stop_all_runners(
    runners: Iterable[Runner],
    status: Status,
    logger: logging.Logger,
    timeout: float = 60.0,
    warning_every: float = 5.0,
) -> None:
    priorities = sorted(set([r.stop_priority() for r in runners]))
    for priority in priorities:
        logger.info(f"stopping runners of priority {priority}")
        prunners = [r for r in runners if r.stop_priority() == priority]
        _stop_runners_batch(prunners, status, logger, timeout, warning_every)


class Manager:
    """
    A manager is the "entry point" of any application using
    the nightskyrunner package.
    A manager uses an instance of [ManagerConfigGetter]() to
    create instances of [factories.RunnerFactory](). It then uses
    these factories to create and start instances of [runner.Runner]().
    Upon the call to its [Manager.start]() method, the manager spawns a thread
    which iterates based on its core frequency (1Hz by default).

    At each iteration, the [ManagerConfigGetter.get]() method
    of the manager config getter
    is called, which returns a list of runner factories.
    Each runner factory corresponds to a runner that should be up and running
    according to the logic of the concrete subclass
    of [ManagerConfigGetter]() instance passed as argument.
    This logic may result in a different list of runner factories
    being returned at each call to the [Manager.iterate] method.
    The manager will create, start, stop or revive
    instances of [runner.Runner]() accordingly.

    Instances of Manager can be created via a context manager,
    ensuring all instances of [runner.Runner]() are stopped
    at exit. The start method of the manager is automatically called
    at instanciation, and its stop method called upon exit of the
    context manager.

    ```
    with Manager(manager_config_getter) as manager:
      while True:
        try:
            time.sleep(0.2)
        except KeyboardInterrupt:
            break
    ```

    Arguments:
      manager_config_getter: concrete instance of a subclass of
        [ManagerConfigGetter]()
      name: arbirary string, used only by the logger
      core_frequency: frequency at which the iterate method will
        be called (i.e. instances of [runner.Runner]() will be
        destroyed, revived or created)
      keep_shared_memory: if True, the shared memory will not be
        cleaned up during exit. Note that the shared memory uses
        sockets, and these sockets will then not be cleanup up as
        they should. To use only for testing purposed.
    """

    def __init__(
        self,
        manager_config_getter: ManagerConfigGetter,
        name: str = "nightskyrunner",
        core_frequency: float = 1.0,
        keep_shared_memory: bool = False,
    ) -> None:
        self._name = name
        self._config_getter = manager_config_getter
        self._runners: Dict[RunnerFactory, Runner] = {}
        self._running: bool = False
        self._core_frequency = core_frequency
        self._thread: Optional[Thread] = None
        self._status = Status(self._name, "Manager")
        self._logger = logging.getLogger(name)
        self._keep_shared_memory = keep_shared_memory

    def _iterate(self) -> None:
        _update_runners(self._runners, self._config_getter, self._logger)

    def alive(self) -> bool:
        if self._thread is None or not self._thread.is_alive():
            return False
        return True

    def _run(self) -> None:
        self._running = True
        self._status.state(State.running)
        while self._running:
            try:
                self._iterate()
            except Exception as e:
                error_str = get_error_info(e)
                self._logger.error(error_str)
                self._status.state(State.error, error_str)
            else:
                self._status.state(State.running)
            time.sleep(1.0 / self._core_frequency)
        self._state = self._status.state(State.stopping)
        _stop_all_runners(self._runners.values(), self._status, self._logger)
        self._state = self._status.state(State.off)

    def start(self) -> None:
        """
        Starts the manager, i.e. the periodic calls to
        an iterate function which will start or stop
        instances of [runner.Runner]().
        """
        self._logger.info("starting")
        self._thread = Thread(target=self._run)
        self._state = self._status.state(State.starting)
        self._thread.start()
        self._logger.info("started")

    def stop(self) -> None:
        """
        Stops all the [runner.Runner]()
        and clears the shared memory.
        """
        if self._thread is not None:
            self._logger.info("stopping")
            self._running = False
            self._thread.join()
            self._thread = None
            self._logger.info("stopped")
        if not self._keep_shared_memory:
            SharedMemory.stop()

    def __enter__(self) -> "Manager":
        self.start()
        return self

    def __exit__(self, _, __, ___) -> None:
        self.stop()
