import json
import time

import click
import numpy as np
import redis
from structlog import get_logger

PAYLOAD = b"1" * 100
logger = get_logger()


@click.command()
@click.option("--load", required=True, type=click.Path(exists=True))
@click.option("--redis-ip", default="0.0.0.0")
@click.option("--redis-port", required=True, default=7000, type=int)
def load_gen(load, redis_ip, redis_port):
    deltas = np.load(load)
    r = redis.Redis(redis_ip, redis_port, decode_responses=True)

    get_num_workers = lambda: len(
        json.loads(r.execute_command("mantis.status"))["queues"]
    )
    while get_num_workers() == 0:
        logger.msg("Zero worker available, waiting...")
        time.sleep(1)

    total_load = len(deltas)
    log_every = total_load // 100
    for i, delta in enumerate(deltas):
        if i % log_every == 0:
            logger.msg(f"Sent {i} queries", percent=i / total_load)
        r.execute_command("mantis.enqueue", PAYLOAD, time.time(), i)
        time.sleep(delta / 1000)

    logger.msg("Load generation finished!")
