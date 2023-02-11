from . import status
from . import configcheck
from .config_getter import ConfigGetter


class Runner(status.Status):
    def __init__(self, name: str, config: ConfigGetter) -> None:
        super().__init__(name)
        self._config = config

    def check_config(self, template: configcheck.ConfigTemplate) -> None:
        configcheck.check_configuration(template, self._config)

    def iterate(self):
        raise NotImplementedError()

    def run(self):
        raise NotImplementedError()


class ThreadRunner(Runner):
    def __init__(self, name: str, config: Config) -> None:
        super().__init__(name, config)

    def run(self):
        pass
