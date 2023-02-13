import time
import multiprocessing
from nightskyrunner import shared_memory


class P:
    def __init__(self):
        self._running = multiprocessing.Value("i", False)
        self._process: typing.Optional[multiprocessing.Process] = None
        self._sm = shared_memory.root()

    def _run(self,sm):
        self._running.value = True
        count = 0
        while self._running.value:
            count += 1
            sm.item("a",exists_ok=True).set(count)
            print(
                sm.item("a",exists_ok=True).get()
            )
            time.sleep(0.1)
            
    def start(self) -> None:
        self._process = multiprocessing.Process(target=self._run, args=(shared_memory.root(),))
        self._process.start()

    def stop(self):
        if self._process is not None:
            self._running.value = False
            self._process.join()
            self._process = None


p = P()
p.start()

sm = shared_memory.root()

for _ in range(20):
    print(
        "\t",
        sm.item("a",exists_ok=True).get()
    )
    time.sleep(0.1)

p.stop()
