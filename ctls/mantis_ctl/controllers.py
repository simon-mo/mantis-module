from typing import List

import numpy as np


class Controller:
    def get_action_from_state(
        self,
        # List[float] in ms
        e2e_latency_since_last_call: List[float],
        interarrival_deltas_ms_since_last_call,  # np.diff(real_ts_ns) / 1e3
        current_number_of_replicas,  # Only active replicas count
        queue_length,  # Sum(active replicas queue length)
    ):
        pass


class PID:
    model_processing_time_s = 0.02

    # Sigma is the expected arrival_rate/service_rate
    target_sigma = 0.4

    # PID parameters
    k_p = 1
    k_i = 0
    k_d = 0

    def get_action_from_state(self, lats, deltas, num_replicas, queue_length):
        num_queries_arrived = len(deltas)
        num_queries_served = len(lats)

        if num_queries_arrived == num_queries_served == 0:
            return 0

        # Compute lambda
        past_duration_s = 5
        # alternative formulation
        # past_duration_s = np.sum(deltas)/1000
        mean_arrival_rate = num_queries_arrived / past_duration_s

        # Compute mu
        model_expected_qps = 1 / self.model_processing_time_s
        mean_service_rate = num_replicas * model_expected_qps

        # Compute delta hat
        sigma_hat = mean_arrival_rate / mean_service_rate
        # Target changes
        e_t = sigma_hat - self.target_sigma
        # Num replica for changes
        action = self.k_p * e_t

        return action


class BangBang:
    slo = 150  # ms
    low = 0.5 * slo
    high = 0.8 * slo

    def get_action_from_state(self, lats, deltas, num_replicas, qlen):
        if len(lats) == 0:
            return 0
        p99 = np.percentile(lats, 99)
        if p99 < self.low:
            return -0.8
        if p99 > self.high:
            return 0.8
        return 0
