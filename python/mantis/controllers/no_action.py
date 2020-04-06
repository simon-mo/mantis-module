from mantis.controllers.base import BaseController


class DoNothingController(BaseController):
    def get_action_from_state(
        self,
        e2e_latency_since_last_call,
        interarrival_deltas_ms_since_last_call,
        current_number_of_replicas,
        queue_length,
    ):
        return 0
