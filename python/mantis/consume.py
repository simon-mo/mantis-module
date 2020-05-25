import json
import random
import signal
import sys
import time
import uuid
import threading
import os

import click
import redis
import pykube
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


HEALTH_CHECK_DURATION_S = 20 / 1e3


class HealthCheckSender(threading.Thread):
    def __init__(self, redis_ip, redis_port, my_uuid):
        self.r = redis.Redis(redis_ip, port=redis_port, decode_responses=True)
        self.my_id = my_uuid
        super().__init__()

    def run(self):
        while not thread_should_stop.is_set():
            time.sleep(HEALTH_CHECK_DURATION_S)
            self.run_once()

    def run_once(self):
        self.r.execute_command("mantis.health", self.my_id)


class PodStatusChecker(threading.Thread):
    def __init__(self, on_terminating_status):
        self.api = pykube.HTTPClient(pykube.KubeConfig.from_env())
        self.my_name = os.environ["MY_POD_NAME"]
        self.callback = on_terminating_status
        super().__init__()

    def run(self):
        while not thread_should_stop.is_set():
            time.sleep(5)
            self.run_once()

    def run_once(self):
        query = pykube.Pod.objects(self.api).filter(
            field_selector={"metadata.name": self.my_name}
        )
        result = list(query)[0]
        phase = result.obj["status"]["phase"]
        if phase == "Terminating":
            logger.msg("Current status is Terminating, shutting down...")
            self.callback()


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
    worker = None

    while not r.get("worker_should_go"):
        logger.msg("Waiting for worker_should_go signal")
        time.sleep(1)

    sleeper_thread = None
    if is_fractional:
        sleeper_thread = FractionalValueMonitor(redis_ip, redis_port)
        sleeper_thread.start()

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
            thread_should_stop.set()
            if sleeper_thread:
                sleeper_thread.join()
            health_checker.join()
            status_checker.join()
            sys.exit(0)

    # Handle SIGTERM
    def sigterm_wrapper(*args):
        logger.msg("SIGTERM caught")
        signal_handler()

    signal.signal(signal.SIGTERM, sigterm_wrapper)
    signal.signal(signal.SIGHUP, lambda *args: logger.msg("SIGUP caught"))

    logger.msg("Signal handler installed")

    # Delaying instantation of worker since it might take time
    worker = catalogs[workload](**init_args)

    health_checker = HealthCheckSender(redis_ip, redis_port, queue_name)
    health_checker.start()
    logger.msg("Health checker started")

    status_checker = PodStatusChecker(signal_handler)
    status_checker.start()
    logger.msg("K8s pod status checker started")

    r.execute_command("mantis.add_queue", queue_name)
    logger.msg("Queue added to redis")

    try:
        while True:
            if is_fractional and sleeper_thread.try_sleep():
                continue
            next_query = r.blpop(queue_name, timeout=1)
            if next_query is None:
                # logger.msg("Timeout, retrying...")
                continue
            # if not None, next_query is format (key, value)
            _, next_query = next_query
            work_on_single_query(next_query)
            next_query = None
    # Handle SIGINT
    except KeyboardInterrupt:
        logger.msg("SIGINT caught")
        signal_handler()
