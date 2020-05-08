import time
import hashlib


class Sleeper:
    def __init__(self, sleep_time_s):
        self.sleep_time = float(sleep_time_s)

    def __call__(self, *args):
        time.sleep(self.sleep_time)

    @staticmethod
    def generate_workload():
        return ""


class BusySleeper(Sleeper):
    def __call__(self, *args):
        start = time.perf_counter()
        while True:
            hashlib.sha256(b"").hexdigest()
            end = time.perf_counter()
            if end - start >= self.sleep_time:
                break
