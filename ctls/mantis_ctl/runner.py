import subprocess
import time
import json

import numpy as np
import redis
from structlog import get_logger
from mantis_ctl.event_metrics import MetricConnection

from mantis_ctl.controllers import PID

ctl = PID()

if __name__ == "__main__":
    RESULT_KEY = "completion_queue"
    logger = get_logger()
    r = redis.Redis("redis-service", port=7000, decode_responses=True)
    conn = MetricConnection("/tmp/metric.db")

    def scale(new_reps):
        # Set integer component
        new_reps = max(new_reps, 1)

        exit_code = subprocess.call(
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
        assert exit_code == 0

        # Set fracitonal component
        r.set("fractional_prob", str(new_reps % 1.0))
        logger.msg("Setting ", fractional_value=str(new_reps % 1.0))

    while True:
        # Latency list
        length_to_pop = r.llen(RESULT_KEY)
        conn.observe("num_queries_served", length_to_pop)

        summary = []
        for _ in range(length_to_pop):
            __, val = r.blpop(RESULT_KEY)
            parsed_msg = json.loads(val)
            e2e_latency = float(parsed_msg["_4_done_time"]) - (parsed_msg["_1_lg_sent"])
            conn.observe("e2e_latency", e2e_latency)
            summary.append(e2e_latency)
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
            "dropped_queue_sizes",
            "current_time_ns",
        ]
        [decoded_msg.pop(metric) for metric in non_scaler_metric]
        logger.msg("Gathered metrics...", **decoded_msg)

        curr_int_reps = msg["num_active_replica"] - 1
        fractional_value = msg["fractional_value"]
        curr_reps = curr_int_reps + fractional_value
        conn.observe("current_replicas", curr_reps)

        action = ctl.get_action_from_state(
            np.array(summary) * 1000,
            np.array(msg["real_ts_ns"]) / 1000,
            curr_reps,
            sum(msg["queue_sizes"]),
        )
        conn.observe("total_queue_size", sum(msg["queue_sizes"]))
        conn.observe("dropped_queue_size", sum(msg["dropped_queue_sizes"]))
        target_reps = curr_reps + action
        conn.observe("action", action)
        conn.observe("target_replicas", target_reps)
        logger.msg("Scaling to", from_=curr_reps, to_=target_reps, delta=action)

        scale(target_reps)

        time.sleep(5)
