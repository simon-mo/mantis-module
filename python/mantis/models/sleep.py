import time


class Sleeper:
    def __init__(self, sleep_time_s):
        self.sleep_time = sleep_time

    def __call__(self, *args):
        time.sleep(self.sleep_time)

    @staticmethod
    def generate_workload():
        return ""
