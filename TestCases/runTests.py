#!/usr/bin/env python3
import snappy_step
from contextlib import chdir
import os

items = os.listdir()
failed = []
completed = []
for item in items:
    if not os.path.isdir(os.path.join(item)):
        continue
    else:
        print("running " + item)
        with chdir(os.path.join(item)):
            try:
                snappy_step.main_func()
                completed.append(item)
            except:
                failed.append(item)
                print(item + " Failed.")
                snappy_step.snappy_step_cleanup()
        


print(str(len(failed)) + " case(s) failed.")
print(*failed)
print(str(len(completed)) + " case(s) completed.")
print(*completed)