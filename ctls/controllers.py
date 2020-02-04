import subprocess
import time
import json
from typing import List

import click
import numpy as np
import redis
from structlog import get_logger


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
        # Compute lambda
        num_queries = len(lats)
        past_duration_s = 5
        # alternative formulation
        # past_duration_s = np.sum(deltas)/1000
        mean_arrival_rate = num_queries / past_duration_s

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


if __name__ == "__main__":
    RESULT_KEY = "completion_queue"
    logger = get_logger()
    r = redis.Redis("redis-service", port=7000, decode_responses=True)

    def scale(new_reps):
        # Set integer component
        result = subprocess.call(
            " ".join(
                [
                    "kubectl",
                    "scale",
                    "--replicas={}".format(int(new_reps)),
                    "deploy/mantis-worker",
                ]
            ),
            shell=True,
        )
        assert result == 0

        # Set fracitonal component
        r.set("fractional_prob", str(result % 1.0))

    ctl = BangBang()
    while True:
        # Latency list
        length_to_pop = r.llen(RESULT_KEY)
        summary = []
        for _ in range(length_to_pop):
            __, val = r.blpop(RESULT_KEY)
            parsed_msg = json.loads(val)
            summary.append(
                float(parsed_msg["_4_done_time"]) - (parsed_msg["_1_lg_sent"])
            )
        if len(summary):
            percentiles = [25, 50, 95, 99, 100]
            logger.msg(
                "Received {} from last interval".format(len(summary)),
                **dict(zip(map(str, percentiles), np.percentile(summary, percentiles)))
            )
        else:
            logger.msg("No result received in 5sec")

        val = r.execute_command("mantis.status")

        decoded_msg = json.loads(val)
        msg = json.loads(val)
        non_scaler_metric = [
            "real_ts_ns",
            "queues",
            "queue_sizes",
            "dropped_queues",
        ]
        [decoded_msg.pop(metric) for metric in non_scaler_metric]
        logger.msg("Gathered metrics...", **decoded_msg)

        curr_reps = msg["num_active_replica"]
        action = ctl.get_action_from_state(
            lats=np.array(summary) * 1000,
            deltas=np.array(msg["real_ts_ns"]) / 1000,
            num_replicas=msg["num_active_replica"],
            qlen=sum(msg["queue_sizes"]),
        )
        target_reps = curr_reps + action
        scale(target_reps)

        time.sleep(5)
