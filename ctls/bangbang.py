import subprocess
import time
import json

import click
import numpy as np
import redis
from structlog import get_logger

class Controller:
    def get_action_from_state(self,
            e2e_latency_since_last_call, # List[float] in ms , todo
            interarrival_deltas_ms_since_last_call, # np.diff(real_ts_ns) / 1e3
            current_number_of_replicas, # Only active replicas count
            queue_length # Sum(active replicas queue length)
            ):
        pass

class BangBang:
    slo = 150 #ms
    low = 0.5 * slo
    high = 0.8 * slo

    def get_action_from_state(self, lats, deltas, num_replicas, qlen):
        if len(lats) == 0: return 0
        p99 = np.percentile(lats, 99)
        if p99 < self.low:
            return -1
        if p99 > self.high:
            return 1
        return 0

def scale(new_reps):
    result = subprocess.call(' '.join(['kubectl', 'scale', '--replicas={}'.format(int(new_reps)), 'deploy/mantis-worker']), shell=True)
    assert result == 0

ctl = BangBang()
RESULT_KEY = "completion_queue"
logger = get_logger()


r = redis.Redis("0.0.0.0", port=7000, decode_responses=True)
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
            lats=np.array(summary)*1000, 
            deltas=np.array(msg["real_ts_ns"])/1000, 
            num_replicas=msg["num_active_replica"], 
            qlen=sum(msg["queue_sizes"])
            )
    target_reps = curr_reps + action
    scale(target_reps)

    time.sleep(5)
