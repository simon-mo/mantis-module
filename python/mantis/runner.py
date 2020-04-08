import subprocess
import random
import string
import time
import json
import os
from pathlib import Path
import sqlite3

import numpy as np
import redis
from structlog import get_logger
import click
import pykube
import yaml

from mantis.models import catalogs
from mantis.controllers import registry


logger = get_logger()
logger.bind(role="runner")

K8S_DIR = Path(__file__).parent / "k8s"
RESULT_KEY = "completion_queue"
REDIS_PORT = 7000


def random_letters(length=10):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


class K8sClient:
    def __init__(self):
        config = pykube.KubeConfig.from_env()
        self.k8s_api = pykube.HTTPClient(config)

    def recreate_resource(self, resource, spec):
        k8s_obj = resource(self.k8s_api, spec)
        k8s_obj.delete()
        k8s_obj.create()

    def create_redis(self):
        with open(K8S_DIR / "1_redis.yaml") as f:
            loaded = list(yaml.load_all(f, Loader=yaml.FullLoader))
        deploy, service = loaded
        redis_name = service["metadata"]["name"]

        self.recreate_resource(pykube.Deployment, deploy)
        self.recreate_resource(pykube.Service, service)

        while os.system(f"redis-cli -h redis-service -p 7000 ping") != 0:
            logger.msg("Waiting for redis to become avaiable")
            time.sleep(2)

        return redis_name

    def create_workers(self, redis_name, workload, workload_args):
        with open(K8S_DIR / "2_worker.yaml") as f:
            workers, frac_worker = list(yaml.load_all(f, Loader=yaml.FullLoader))
        envvars = [
            {"name": "MANTIS_REDIS_IP", "value": redis_name},
            {"name": "MANTIS_WORKLOAD", "value": workload},
            {"name": "MANTIS_CUSTOM_ARGS", "value": workload_args},
        ]
        workers["spec"]["template"]["spec"]["containers"][0]["env"] = envvars
        frac_worker["spec"]["containers"][0]["env"] = envvars
        frac_worker["metadata"]["name"] += "-" + random_letters()

        self.recreate_resource(pykube.Deployment, workers)
        self.recreate_resource(pykube.Pod, frac_worker)

        def worker_states():
            worker_pods = list(
                pykube.Pod.objects(self.k8s_api).filter(selector={"app": "worker"})
            )
            worker_pods.append(
                pykube.Pod.objects(self.k8s_api).get_by_name(
                    frac_worker["metadata"]["name"]
                )
            )
            states = {pod.name: pod.ready for pod in worker_pods}
            return states

        states = worker_states()
        while not all(states.values()):
            logger.msg(f"Waiting for all worker to become ready: {states}")
            time.sleep(2)
            states = worker_states()

        self.worker_deploy_name = workers["metadata"]["name"]

    def scale_workers(self, new_integer):
        assert hasattr(self, "worker_deploy_name")
        deploy = pykube.Deployment.objects(self.k8s_api).get_by_name(
            self.worker_deploy_name
        )
        deploy.scale(int(new_integer))

    def create_load_generator(self, redis_name, workload, load_file):
        with open(K8S_DIR / "4_load_gen.yaml") as f:
            [gen] = list(yaml.load_all(f, Loader=yaml.FullLoader))
        env = [
            {"name": "MANTIS_REDIS_IP", "value": redis_name},
            {"name": "MANTIS_WORKLOAD", "value": workload},
            {"name": "MANTIS_LOAD_FILE", "value": load_file},
        ]
        gen["spec"]["template"]["spec"]["containers"][0]["env"] = env
        self.recreate_resource(pykube.Job, gen)


class MetricConnection:
    def __init__(self):
        self.path = "./mantis_result_{}.db".format(int(time.time()))
        self.conn = sqlite3.connect(self.path, isolation_level=None)
        self.conn.execute("pragma synchronou=0")


# TODO: finish this ^


@click.command()
@click.option("--load", required=True, type=click.Path(exists=True))
@click.option("--workload", required=True, type=click.Choice(list(catalogs.keys())))
@click.option("--workload-args", default="", type=str)
@click.option("--controller", required=True, type=click.Choice(list(registry.keys())))
def run_controller(load, workload, controller, workload_args):
    client = K8sClient()
    ctl = registry[controller]()

    logger.msg("Creating redis")
    redis_ip = client.create_redis()

    r = redis.Redis(redis_ip, port=7000, decode_responses=True)
    r.set("fractional_sleep", str(0.02))
    r.set("fractional_prob", str(0.02))

    logger.msg("Creating workers")
    client.create_workers(redis_ip, workload="sleep", workload_args=workload_args)

    logger.msg("Creating load generator")
    client.create_load_generator(
        redis_ip, workload="sleep", load_file="/data/Auckland-10min.npy"
    )

    # Let workers and load gen starts
    r.set("worker_should_go", "true")
    r.set("load_gen_should_go", "true")

    def scale(new_reps):
        new_reps = max(new_reps, 1)
        new_reps = min(new_reps, 32)

        # Set integer component
        client.scale_workers(int(new_reps))
        # Set fracitonal component
        frac_val = str(new_reps % 1.0)
        r.set("fractional_prob", frac_val)
        logger.msg(f"Setting fractional_value={frac_val}")

    while True:
        # Latency list
        length_to_pop = r.llen(RESULT_KEY)
        # conn.observe("num_queries_served", length_to_pop)

        summary = []
        for _ in range(length_to_pop):
            __, val = r.blpop(RESULT_KEY)
            parsed_msg = json.loads(val)
            e2e_latency = float(parsed_msg["_4_done_time"]) - (parsed_msg["_1_lg_sent"])
            # conn.observe("e2e_latency", e2e_latency)
            summary.append(e2e_latency)
        if len(summary):
            percentiles = [25, 50, 95, 99, 100]
            logger.msg(
                "Received {} from last interval".format(len(summary)),
                **dict(zip(map(str, percentiles), np.percentile(summary, percentiles))),
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
        # conn.observe("current_replicas", curr_reps)

        action = ctl.get_action_from_state(
            np.array(summary) * 1000,
            np.array(msg["real_ts_ns"]) / 1000,
            curr_reps,
            sum(msg["queue_sizes"]),
        )
        # conn.observe("total_queue_size", sum(msg["queue_sizes"]))
        # conn.observe("dropped_queue_size", sum(msg["dropped_queue_sizes"]))
        target_reps = curr_reps + action
        # conn.observe("action", action)
        # conn.observe("target_replicas", target_reps)
        logger.msg("Scaling to", from_=curr_reps, to_=target_reps, delta=action)

        scale(target_reps)

        time.sleep(5)
