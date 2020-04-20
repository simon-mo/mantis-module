from mantis.controllers.base import BaseController

import random


class DoNothingController(BaseController):
    # Use for debugging, do nothing
    def get_action_from_state(
        self,
        e2e_latency_since_last_call,
        interarrival_deltas_ms_since_last_call,
        current_number_of_replicas,
        queue_length,
    ):
        return 0


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
