from . import status
from . import configcheck

class Runner(status.Status):

    def __init__(
            self,
            name: str,
            config: configcheck.Config
    )->None:
        super().__init__(name)
        self._config = config

    def check_config(self, template: configcheck.ConfigTemplate)->None:
        configcheck(
            template, self._config
        )
        
    def iterate(self):
        raise NotImplementedError()

    def run(self):
        raise NotImplementedError()

    
class ThreadRunner(Runner):
    
    def __init__(self, name: str)->None:
        super().__init__(name)

    def run(self):
    
