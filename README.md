[![Python package](https://github.com/MPI-IS/nightskyrunner/actions/workflows/tests.yml/badge.svg)](https://github.com/MPI-IS/nightskyrunner/actions/workflows/tests.yml)
[![PyPI version](https://img.shields.io/pypi/v/nightskyrunner.svg)](https://pypi.org/project/nightskyrunner/)


> 🚧 **Under Construction**  
> This project is currently under development. Please check back later for updates.


# nightskyrunner

A package for spawning resilient threads and processes from TOML configuration files.

## Overview

This package focuses on the instantiation of custom threads and processes based on TOML configuration files.
To use nightskyrunner, a developer must:

- write the code of custom runner classes (i.e. classes with an iterate function that has to be called periodically).
- write a TOML configuration listing the runners classes to instantiate and run.
- instantiate in its code an instance of nightskyrunner Manager, which will parse the TOML file and spawn the corresponding threads and processes which will run in the background.

## Why nightskyrunner

Nightskyrunner focuses on:

- Resilience: if the iterate function of a runner raises an error, the manager will regularly attempt to revive the runner.
- Reconfiguration:
    - The toml configuration file used by the manager can be edited during runtime. For example, if new runners are added, the manager will instantiate them without need the encapsulating script to restart.
    - Each runner can also be associated to its own toml configuration file. The configuration is parsed at each iteration, i.e. changes in the toml file will reconfigure the runner without need the encapsulating script to restart.

Nightskycam also supports:

- Communication between runners: this is not what nightskyrunner is especially good at, but at least some basic shared memory operations are supported.
- Runner status monitoring: runners can share various information regarding their health and activity via their status attribute, which live in the shared memory (i.e. can be accessed by other runners)

## Getting Started as a User (using `pip`)

Dependency management with `pip` is easier to set up than with `poetry`, but the optional dependency-groups are not installable with `pip`.

* Create and activate a new Python virtual environment:
  ```bash
  python3 -m venv --copies venv
  source venv/bin/activate
  ```
* Update `pip` and build package:
  ```bash
  pip install -U pip  # optional but always advised
  pip install .       # -e option for editable mode
  ```

## Getting Started as a Developer (using `poetry`)

Dependency management with `poetry` is required for the installation of the optional dependency-groups.

* Install [poetry](https://python-poetry.org/docs/).
* Install dependencies for package
  (also automatically creates project's virtual environment):
  ```bash
  poetry install
  ```
* Install `dev` dependency group:
  ```bash
  poetry install --with dev
  ```
* Activate project's virtual environment:
  ```bash
  poetry shell
  ```

## Tests (only possible for setup with `poetry`, not with `pip`)


To install `test` dependency group:
```bash
poetry install --with test
```

To run the tests:
```bash
python -m pytest
```

## Building the documentation (only possible for setup with `poetry`, not with `pip`)

To install `doc` dependency group:
```bash
poetry install --with doc
```

To build the documentation:
```bash
mkdocs build  # will create a "site" subfolder with the html files
```

or

```bash
mkdocs serve  # will spawn a local server 
```

## How to use

### (1) create subclass(es) of ThreadRunner or ProcessRunner

In your package, create a module, and then the code for a runner.

```python

from nightskyrunner.status import Status, level
from nightskyrunner.runner import ProcessRunner
from nightskyrunner.shared_memory import SharedMemory

@status_error  # required
class MyRunner(ProcessRunner):  # or ThreadRunner

    # no need to concern yourself with these arguments,
    # the manager will pass suitable values when
    # creating the instances
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

        # to be sure this shared memory segment
        # will be propery accessible by other runners,
        # devs have to initialize them in the runner's
        # constructor
        memory = SharedMemory.get("mymemory")
        # memory is a proxy to a shared dictionary
        # from the multprocessing package.Values can be only
        # basic types.
        memory["myvalue"] = 0
        # for demonstration purposes
        self.iteration = 0

    def on_exit(self):
        # type here code that should be executed
        # when the runner exits
        ...

    def iterate(self) -> None:

        # iterate is core function that will be called at the frequency
	# set in the runner's configuration (see later in this
        # tutorial).

	# 'log_status' should also be set in the runner's configuration
	log_status = int(self._config_getter.get()["log_status"])

        # this will finds its ways to the logs
        # (see later this tutorial how logs can be configured)
        self.log(Level.info, f"logging the status: {log_status}")

        # other runners can write/access this with a similar line of code
        # here changing the value.
        memory = SharedMemory.get("mymemory")["myvalue"] = 5

        # the status attributes is another way of sharing info with
        # the world. For example:
        self.iteration += 1
        try:
            # could have been set by another runner
            othervalue = SharedMemory("othermemory")["othervalue"]
        except KeyError:
            othervalue = None
            error = "failed to read the othermemory/othervalue memory"
            self.log(Level.debug, error)
            self._status.set_issue(error)
        else:
            # an issue could have been set during a previous iteration, but now
            # all are fine
            self._status.remove_issue()
        values = {
            "iteration": self.iteration,
            "log_status": log_status,
            "othervalue": othervalue,
	    "myvalue": myvalue
        }
        self._status.values(values)

        # getting the status of the other runners, to save them in a file
        # (for demonstration purposes)
	if log_status:
	  self._status.activity(
            "logging the status"
          )  # to track with this runner is doing
          all_status: List[Status] = Status.retrieve_all()
	  for s in all_status:
	    dict_status = s.get()
	    self.log(Level.debug, f"status for {dict_status['name']}: {repr(dict_status)}")
```

### (2) create a configuration file for your runner

Create a toml file (e.g. myrunner1.toml):

```toml
frequency = 1.0
log_status = true
```

You can see in the code of MyRunner that the iterate function
requires a configuration value for 'myconfig'.
The frequency key is also required. Here it will set the instance
of MyRunner to run at 1Hz.

### (3) create a configuration file for the manager

Create another toml file, called for example manager.toml:

```toml
[myrunner1]
class_runner = "mypackage.mymodule.MyRunner"
class_config_getter = "nightskyrunner.config_toml.DynamicTomlConfigGetter"
args = ["myrunner1.toml"]

[myrunner2]
class_runner = "mypackage.mymodule.MyRunner"
class_config_getter = "nightskyrunner.config_toml.DynamicTomlConfigGetter"
args = ["myrunner2.toml"]
```

This configuration file will request the manager to spawn two instances
of MyRunner, called 'myrunner1' and 'myrunner2'.
If it can not be assumed that 'myrunner1.toml' and 'myrunner2.toml' are
in the same directory as 'manager.toml', absolute file paths should be used.

It is assumed that "mypackage.mymodule.MyRunner" is on the python path
(e.g. that 'mypackage' has been (pip) installed).

'DynamicTomlConfigGetter' is a class that will parse the toml configuration
file at each iteration of the runner, i.e. the value of myconfig

```python
myconfig = int(self._config_getter.get()["myconfig"])
```

may differ between iterations if the content of 'myrunner1.toml' (or
'myrunner2.toml') is edited.

Alternatively, you may use the class ```StaticTomlConfigGetter```,
which will read the toml file only once at startup.

### (4) create an executable or instantiate a Manager in your code

For example:

```python
import time
from pathlib import Path
from nightskyrunner.config_toml import DynamicTomlManagerConfigGetter
from nightskyrunner.manager import Manager
from nightskyrunner.log import set_logging
from nightskyrunner.status import Level

# display info in the current terminal
stdout = True
set_logging(stdout, level=Level.debug)

manager_toml = Path(__file__).parent.resolve() / "manager.toml"

# manager.toml will be parsed continuously.
# alternatively you can use the class TomlManagerConfigGetter
manager_config_getter = DynamicTomlManagerConfigGetter(manager_toml)

with Manager(manager_config_getter) as manager:
    while True:
        try:
            time.sleep(0.2)
        except KeyboardInterrupt:
            break
```

when the context manager is entered, the two instances of MyRunner
(myrunner1 and myrunner2) will be be spawned and will start running
in the backgroud


### (5) play with the configurations

To explore nightskyrunner possibilities, edit the values of the files myrunner1.toml,
myrunner2.toml or manager.toml.

For example, if you change myrunner1.toml from:

```toml
frequency = 1.0
log_status = true
```

to:

```toml
frequency = 0.5
log_status = false
```

myrunner1 will start iterating every 2 seconds, and will stop logging the status.

If you change the configuration to:

```toml
frequency = "invalid frequency"
log_status = false
```

myrunner1 will log some error message. It will stop doing so once
a correct value as been set again for the frequency.


You may also edit the file manager.toml at runtime. For example if you
edit it from:


```toml
[myrunner1]
class_runner = "mypackage.mymodule.MyRunner"
class_config_getter = "nightskyrunner.config_toml.DynamicTomlConfigGetter"
args = ["myrunner1.toml"]

[myrunner2]
class_runner = "mypackage.mymodule.MyRunner"
class_config_getter = "nightskyrunner.config_toml.DynamicTomlConfigGetter"
args = ["myrunner2.toml"]
```

to:

```toml
[myrunner1]
class_runner = "mypackage.mymodule.MyRunner"
class_config_getter = "nightskyrunner.config_toml.DynamicTomlConfigGetter"
args = ["myrunner1.toml"]
```

myrunner2 will stop. Alternatively you can edit the file to start new runners.

## Demo

To run the demo, after (pip) installing nightskyrunner: 

```bash
cd demo
python run.py
```

ctrl+c to exit.

## FAQ

- What is the difference between a ThreadRunner and a ProcessRunner ?

A thread runner is based on the threading package and a process runner on the
multiprocessing package. A ProcessRunner is a separate process, possibly running on another CPU,
but which, contrary to a ThreadRunner, has a separated namespace.

- How to share configuration values between runners ?

Create a toml file (for example vars.toml) with the shared data, e.g.

```toml
shared1 = 1
shared2 = "lala"
```

Update the runner toml file to use [https://jinja.palletsprojects.com][jinja2] template:

```toml
frequency = 1.0
log_status = true
shared = {{ shared1 }}
```

and pass vars.toml as kwargs to the runner's related configuration in the
manager configuration file:

```toml
[myrunner1]
class_runner = "mypackage.mymodule.MyRunner"
class_config_getter = "nightskyrunner.config_toml.DynamicTomlConfigGetter"
args = ["myrunner1.toml"]
[process_runner.kwargs]
"vars" =  "vars.toml"
```

## Author

- [Vincent Berenz](https://is.mpg.de/person/vberenz)
- Continuous integration setup with the help of the [MPI-IS Software Workshop](https://is.mpg.de/en/software-workshop)

## Copyright

Max Planck Gesellschaft @2024
