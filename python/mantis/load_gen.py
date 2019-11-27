import json
import os
import random
import signal
import sys
import time
import uuid

import click
import numpy as np
import redis
import tqdm

PAYLOAD = b"1" * 100
RESULT_KEY = "completion_queue"


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
        print("Zero worker available, waiting...")
        time.sleep(1)

    for i, delta in tqdm.tqdm(enumerate(deltas)):
        r.execute_command("mantis.enqueue", PAYLOAD, time.time(), i)
        time.sleep(delta / 1000)

    print("Load generation finished!")
