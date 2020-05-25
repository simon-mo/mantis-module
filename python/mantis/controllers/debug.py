from mantis.controllers.base import BaseController, AbsoluteValueBaseController
from mantis.util import logger

import random
from itertools import cycle
import json


class FixedActionController(AbsoluteValueBaseController):
    def __init__(self, action, curr_replicas):
        self.action = int(action)
        self.curr_replicas = int(curr_replicas)

    # Use for debugging, do nothing
    def get_action_from_state(
        self,
        e2e_latency_since_last_call,
        interarrival_deltas_ms_since_last_call,
        current_number_of_replicas,
        queue_length,
    ):
        self.curr_replicas += self.action
        return self.curr_replicas


class RandomAddAndDelete(BaseController):
    # Use for debugging, randomly add and remove workers
    def __init__(self):
        self.should_add = False

    def get_action_from_state(
        self,
        e2e_latency_since_last_call,
        interarrival_deltas_ms_since_last_call,
        current_number_of_replicas,
        queue_length,
    ):
        # Flip add and remove each time
        self.should_add = not self.should_add

        amount = random.choice(list(range(1, 40)))
        if self.should_add:
            return amount
        else:
            return -amount


class AddDeleteFixed(BaseController):
    # Used for microbenchmark
    def __init__(self, amount):
        self.amount = int(amount)
        self.should_add = False

    def get_action_from_state(
        self,
        e2e_latency_since_last_call,
        interarrival_deltas_ms_since_last_call,
        current_number_of_replicas,
        queue_length,
    ):
        self.should_add = not self.should_add

        if self.should_add:
            return self.amount
        else:
            return -self.amount


class Scheduled(AbsoluteValueBaseController):
    def __init__(self, schedule_str, curr_replicas):
        schedule = list(map(int, schedule_str.split("/")))
        logger.msg(f"Created schedule {schedule}")
        self.iterator = cycle(schedule)

        self.curr_replicas = curr_replicas

    def get_action_from_state(
        self,
        e2e_latency_since_last_call,
        interarrival_deltas_ms_since_last_call,
        current_number_of_replicas,
        queue_length,
    ):
        self.curr_replicas += next(self.iterator)
        return self.curr_replicas


def test_scheduler():
    s = Scheduled("1/0/-1/0")
    output = [s.get_action_from_state(None, None, None, None) for _ in range(8)]
    assert output == [1, 0, -1, 0, 1, 0, -1, 0]
