import json
import random
import signal
import sys
import time
import uuid
import threading

import click
import redis
from structlog import get_logger
from mantis.models import catalogs
from mantis.util import parse_custom_args

logger = get_logger()
logger = logger.bind(role="consumer")


RESULT_KEY = "completion_queue"

FRACTIONAL_SLEEP = 0.0
FRACTIONAL_PROB = 0.0
CHECK_DURATION = 2

thread_should_stop = threading.Event()


class FractionalValueMonitor(threading.Thread):
    def __init__(self, redis_ip, redis_port):
        self.r = redis.Redis(redis_ip, port=redis_port, decode_responses=True)
        self.sleep_value = 0.0
        self.prob_value = 0.0
        super().__init__()

    def run(self):
        while not thread_should_stop.is_set():
            time.sleep(CHECK_DURATION)

    def run_once(self):
        new_fractional_prob = float(self.r.get("fractional_prob"))
        new_fractional_sleep = float(self.r.get("fractional_sleep"))

        if self.sleep_value != new_fractional_sleep:
            logger.msg(
                "Fractional sleep time updated",
                old=self.sleep_value,
                new=new_fractional_sleep,
            )
            self.sleep_value = new_fractional_sleep

        if self.prob_value != new_fractional_prob:
            logger.msg(
                "Fractional probability updated",
                old=self.prob_value,
                new=new_fractional_prob,
            )
            self.sleep_prob = new_fractional_prob

    def try_sleep(self):
        if random.random() <= self.prob_value:
            time.sleep(self.sleep_value)
            return True
        return False


@click.command()
@click.option("--redis-ip", default="0.0.0.0", envvar="MANTIS_REDIS_IP")
@click.option("--redis-port", default=7000, type=int)
@click.option("--is-fractional", is_flag=True)
@click.option(
    "--workload",
    required=True,
    type=click.Choice(list(catalogs.keys())),
    envvar="MANTIS_WORKLOAD",
)
@click.option("--custom-args", envvar="MANTIS_CUSTOM_ARGS")
def consume(redis_ip, redis_port, is_fractional, workload, custom_args):
    init_args = dict()
    if custom_args:
        init_args.update(parse_custom_args(custom_args))
    r = redis.Redis(redis_ip, port=redis_port, decode_responses=True)
    queue_name = uuid.uuid4().hex
    logger.msg(f"My queue uuid is {queue_name}")
    worker = catalogs[workload](**init_args)

    while not r.get("worker_should_go"):
        logger.msg("Waiting for worker_should_go signal")
        time.sleep(1)

    sleeper_thread = None
    if is_fractional:
        sleeper_thread = FractionalValueMonitor(redis_ip, redis_port)
        sleeper_thread.start()

    r.execute_command("mantis.add_queue", queue_name)
    logger.msg("Queue added to redis")

    next_query = None

    def work_on_single_query(next_query):
        query = json.loads(next_query)
        query["_3_dequeue_time"] = time.time()
        query["result"] = worker(query.pop("payload"))
        r.execute_command("mantis.complete", json.dumps(query))

    def signal_handler(*args):
        nonlocal next_query
        logger.msg("SIGNAL received, Draining the queue...")
        try:
            r.execute_command("mantis.drop_queue", queue_name)
            thread_should_stop.set()

            if next_query:
                work_on_single_query(next_query)

            items_left = r.llen(queue_name)
            logger.msg("{} item left, processing...".format(items_left))
            for _ in range(items_left):
                if sleeper_thread:
                    sleeper_thread.try_sleep()
                next_query = r.lpop(queue_name)
                work_on_single_query(next_query)
            logger.msg("All done!")
        except Exception as e:
            logger.msg(f"Exception happened while handling draining signal {e}")
        finally:
            sys.exit(0)

    # Handle SIGTERM
    def sigterm_wrapper(*args):
        logger.msg("SIGTERM caught")
        signal_handler()

    signal.signal(signal.SIGTERM, sigterm_wrapper)
    signal.signal(signal.SIGHUP, lambda *args: logger.msg("SIGUP caught"))

    logger.msg("Signal handler installed")

    try:
        while True:
            if is_fractional and sleeper_thread.try_sleep():
                continue
            next_query = r.blpop(queue_name, timeout=1)
            if next_query is None:
                logger.msg("Timeout, retrying...")
                continue
            # if not None, next_query is format (key, value)
            _, next_query = next_query
            work_on_single_query(next_query)
            next_query = None
    # Handle SIGINT
    except KeyboardInterrupt:
        logger.msg("SIGINT caught")
        signal_handler()
