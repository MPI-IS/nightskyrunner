import time
from pathlib import Path

from nightskyrunner.config_toml import DynamicTomlManagerConfigGetter
from nightskyrunner.log import set_logging
from nightskyrunner.manager import Manager
from nightskyrunner.status import Level

stdout = True
set_logging(stdout, level=Level.debug)

manager_toml = Path(__file__).parent.resolve() / "manager.toml"
manager_config_getter = DynamicTomlManagerConfigGetter(manager_toml)

with Manager(manager_config_getter) as manager:
    while True:
        try:
            time.sleep(0.2)
        except KeyboardInterrupt:
            break
