import time
from multiprocessing import Manager, Process

def stuff(d):
    for count in range(10):
        d["a"] = f"lala {count}"
        time.sleep(1)

m = Manager()
d = m.dict()

d["a"] = 1
d["b"] = m.dict()
d["b"]["c"]=2.1

p = Process(target=stuff,args=(d,))
p.start()

start =  time.time()

while time.time()-start < 10:
    print(d["a"])




