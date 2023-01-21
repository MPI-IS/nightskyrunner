"""
Module defining the Config type.
A Config is a dictionary, which values can be also a Config (recursive type).
A Config refers to the configuration of a [runner.Runner](Runner), i.e. a configuration dictionary
a runner can access to during runtime. An instance of Config is usually accessed via the get
function of a [config_getter.ConfigGetter](configuration getter).

For example:

```python
  def iterate(self):
    # iterate function an instance of Runner.
    config: Config = self._config_getter.get()

```
"""

from typing import Any, Dict, Union

Config = Dict[str, Union[Any, "Config"]]
"""
A configuration dictionary.
"""
