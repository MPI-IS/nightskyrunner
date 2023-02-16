from nightskycam.runner import Runner, ThreadRunner, ProcessRunner

class DummyConfigGetter(ConfigGetter):
    pass


class TestRunnerMixin(Runner):

    def __init__(self):
        self.count = 0
        SharedMemory.get("test")["value_out"] = 0
        SharedMemory.get("test")["value_in"] = 0
        
    def iterate(self):
        self.count += 1
        SharedMemory.get("test")["value_out"] = SharedMemory.get("test")["value_in"]


class ThreadTestRunner(ThreadRunner, TestRunnerMixin):

        def __init__(
                self
                config_getter: ConfigGetter
                frequency: float,
                interrupts: Iterable[Callable[[],bool]]=[],
                core_frequency: float = 0.005
        )->None:
            super().__init__(
                self, config_getter, frequency,
                interrupts, core_frequency
            )

class ProcessTestRunner(ProcessRunner, TestRunnerMixin):

        def __init__(
                self
                config_getter: ConfigGetter
                frequency: float,
                interrupts: Iterable[Callable[[],bool]]=[],
                core_frequency: float = 0.005
        )->None:
            super().__init__(
                self, config_getter, frequency,
                interrupts, core_frequency
            )
            
@pytest.fixture
def get_runner(
        request
) -> Generator[Runner, None, None]:

    runner_class = request.param
    
