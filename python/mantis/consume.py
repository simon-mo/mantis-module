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
from mantis.utils import LogEvery


PAYLOAD = b"1" * 100
RESULT_KEY = "completion_queue"


class Worker:
    def __init__(self):
        pass

    def __call__(self, *args):
        time.sleep(0.02)


@click.command()
@click.option("--redis-ip", default="0.0.0.0")
@click.option("--redis-port", required=True, default=7000, type=int)
@click.option("--is-fractional", is_flag=True)
@click.option("--fractional-sleep", type=float)
def consume(redis_ip, redis_port, is_fractional, fractional_sleep):
    if is_fractional:
        assert fractional_sleep is not None

    r = redis.Redis(redis_ip, port=redis_port, decode_responses=True)
    queue_name = uuid.uuid4().hex
    worker = Worker()
    logger = LogEvery(50)

    r.execute_command("mantis.add_queue", queue_name)

    def work_on_single_query(next_query):
        logger.log("Processing queries...")
        query = json.loads(next_query)
        query["_3_dequeue_time"] = time.time()
        worker(query.pop("payload"))
        r.execute_command("mantis.complete", json.dumps(query))

    next_query = None
    fractional_prob = 0.0

    last_print = time.time()

    def signal_handler(*args):
        nonlocal next_query
        print("SIGINT received Draining the queue...")
        r.execute_command("mantis.drop_queue", queue_name)

        print("Currently processing query is ", next_query)
        if next_query:
            work_on_single_query(next_query)

        items_left = r.llen(queue_name)
        print("{} item left, processing...".format(items_left))
        for _ in range(items_left):
            next_query = r.lpop(queue_name)
            work_on_single_query(next_query)
        print("All done!")
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)

    try:
        while True:
            if is_fractional:
                if time.time() - last_print > 10:
                    print("current fractional prob is", fractional_prob)
                    last_print = time.time()
                new_fractional_prob = r.get("fractional_prob")
                fractional_prob = (
                    float(new_fractional_prob)
                    if new_fractional_prob is not None
                    else 0.0
                )

                if random.random() <= fractional_prob:
                    time.sleep(fractional_sleep)
                    continue

            next_query = r.blpop(queue_name, timeout=1)
            if next_query is None:
                print("Timeout, retrying...")
                continue

            # if not None, next_query is format (key, value)
            _, next_query = next_query
            work_on_single_query(next_query)
            next_query = None
    except KeyboardInterrupt:
        signal_handler()
