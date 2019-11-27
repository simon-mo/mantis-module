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


RESULT_KEY = "completion_queue"


@click.command()
@click.option("--redis-ip", default="0.0.0.0")
@click.option("--redis-port", required=True, default=7000, type=int)
def result_writer(redis_ip, redis_port):
    r = redis.Redis(redis_ip, port=redis_port, decode_responses=True)
    logger = LogEvery(1000)
    with open("result.jsonl", "w+") as f:
        while True:
            _, val = r.blpop(RESULT_KEY)
            logger.log("Writing result...")
            f.write(val)
            f.write("\n")


@click.command()
@click.option("--redis-ip", default="0.0.0.0")
@click.option("--redis-port", required=True, default=7000, type=int)
def metric_monitor(redis_ip, redis_port):
    r = redis.Redis(redis_ip, port=redis_port, decode_responses=True)
    logger = LogEvery(1000)
    with open("metric.jsonl", "w+") as f:
        while True:
            val = r.execute_command("mantis.status")
            logger.log("Writing metric...")
            f.write(val)
            f.write("\n")
            time.sleep(1)
