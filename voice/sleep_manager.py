"""
ULTRON V3
Sleep Manager
"""

import time


class SleepManager:


    def __init__(self):

        self.sleeping = False



    def sleep(self):

        self.sleeping = True

        print("ULTRON: Entering sleep mode 😴")



    def wake(self):

        self.sleeping = False

        print("ULTRON: Wake mode activated 🚀")



    def is_sleeping(self):

        return self.sleeping