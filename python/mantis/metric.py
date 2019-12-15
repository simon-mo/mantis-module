import time
import json

import click
import numpy as np
import redis
from structlog import get_logger

RESULT_KEY = "completion_queue"
logger = get_logger()


@click.command()
@click.option("--redis-ip", default="0.0.0.0")
@click.option("--redis-port", required=True, default=7000, type=int)
def result_writer(redis_ip, redis_port):
    r = redis.Redis(redis_ip, port=redis_port, decode_responses=True)
    with open("result.jsonl", "w+") as f:
        while True:
            length_to_pop = r.llen(RESULT_KEY)
            summary = []
            for _ in range(length_to_pop):
                __, val = r.blpop(RESULT_KEY)
                parsed_msg = json.loads(val)
                summary.append(
                    float(parsed_msg["_4_done_time"]) - (parsed_msg["_1_lg_sent"])
                )
                f.write(val)
                f.write("\n")
            if len(summary):
                percentiles = [25, 50, 95, 99, 100]
                logger.msg(
                    "Received {} from last interval".format(len(summary)),
                    **dict(zip(map(str, percentiles), np.percentile(summary, percentiles)))
                )
            else:
                logger.msg("No result received in 5sec")

            time.sleep(5)


@click.command()
@click.option("--redis-ip", default="0.0.0.0")
@click.option("--redis-port", required=True, default=7000, type=int)
def metric_monitor(redis_ip, redis_port):
    r = redis.Redis(redis_ip, port=redis_port, decode_responses=True)
    with open("metric.jsonl", "w+") as f:
        while True:
            val = r.execute_command("mantis.status")

            decoded_msg = json.loads(val)
            non_scaler_metric = [
                "real_ts_ns",
                "queues",
                "queue_sizes",
                "dropped_queues",
            ]
            [decoded_msg.pop(metric) for metric in non_scaler_metric]

            logger.msg("Gathering metrics...", **decoded_msg)

            f.write(val)
            f.write("\n")

            time.sleep(5)
