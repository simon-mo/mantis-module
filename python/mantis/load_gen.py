import json
import time

import click
import numpy as np
import redis
from structlog import get_logger
from mantis.models import catalogs

logger = get_logger()
logger = logger.bind(role="load_generator")


@click.command()
@click.option(
    "--load", required=True, type=click.Path(exists=True), envvar="MANTIS_LOAD_FILE"
)
@click.option(
    "--workload",
    required=True,
    type=click.Choice(list(catalogs.keys())),
    envvar="MANTIS_WORKLOAD",
)
@click.option("--redis-ip", default="0.0.0.0", envvar="MANTIS_REDIS_IP")
@click.option("--redis-port", default=7000, type=int)
def load_gen(load, workload, redis_ip, redis_port):
    deltas = np.load(load)
    payload = catalogs[workload].generate_workload()
    r = redis.Redis(redis_ip, redis_port, decode_responses=True)

    while not r.get("load_gen_should_go"):
        logger.msg("Waiting for load_gen_should_go signal")
        time.sleep(1)

    total_load = len(deltas)
    log_every = total_load // 100
    for i, delta in enumerate(deltas):
        if i % log_every == 0:
            logger.msg(f"Sent {i} queries", percent=f"{i / total_load:.2f}")
        r.execute_command("mantis.enqueue", payload, time.time(), i)
        time.sleep(delta / 1000)

    logger.msg("Load generation finished!")
