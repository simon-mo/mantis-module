import numpy as np

from mantis.controllers.base import BaseController


class PIDController(BaseController):
    # model_processing_time_s = 0.02

    # Sigma is the expected arrival_rate/service_rate
    # target_sigma = 0.4

    # PID parameters
    k_p = 1
    k_i = 0
    k_d = 0

    def __init__(self, model_processing_time_s, target_sigma):
        self.model_processing_time_s = float(model_processing_time_s)
        self.target_sigma = float(target_sigma)

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


def test_pid():
    pid = PIDController(model_processing_time_s=0.5)

    no_action = pid.get_action_from_state([], [], 0, 0)
    assert no_action == 0

    # arrival rate >> service rate
    deltas = np.zeros(100)
    lats = np.zeros(10)
    num_replicas = 10
    increase = pid.get_action_from_state(lats, deltas, num_replicas, 0)
    assert increase > 0

    # arrival rate << service rate
    deltas = np.zeros(1)
    lats = np.zeros(100)
    decrease = pid.get_action_from_state(lats, deltas, num_replicas, 0)
    assert decrease < 0
