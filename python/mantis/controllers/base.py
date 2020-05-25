from typing import List


class BaseController:
    def get_action_from_state(
        self,
        e2e_latency_since_last_call: List[float],  # List[float] in ms
        interarrival_deltas_ms_since_last_call,  # np.diff(real_ts_ns) / 1e3
        current_number_of_replicas,  # Only active replicas count
        queue_length,  # Sum(active replicas queue length)
    ):
        pass


class AbsoluteValueBaseController(BaseController):
    pass
