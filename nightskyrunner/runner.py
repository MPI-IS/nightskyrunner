from . import status



class Runner(status.Status):

    def __init__(
            self,
            name: str,
            config: configuration.Config
    )->None:
        super().__init__(name)
        self._config = config
        



