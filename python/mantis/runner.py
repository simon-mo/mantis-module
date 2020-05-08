import subprocess
import glob
import random
import string
import time
import math
import json
import os
from pathlib import Path
from collections import OrderedDict, Counter
import inspect
from datetime import datetime
from pprint import pformat

import numpy as np
import redis
from structlog import get_logger
import click
import pykube
import yaml
import boto3
import papermill as pm

from mantis.models import catalogs
from mantis.controllers import registry, DONT_SCALE
from mantis.util import parse_custom_args, post_result_to_slack


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
        self.should_delete_queue = []

    def recreate_resource(self, resource, spec):
        k8s_obj = resource(self.k8s_api, spec)
        k8s_obj.delete()
        k8s_obj.create()
        self.should_delete_queue.append(k8s_obj)

    def delete_all_resource(self):
        for resource in self.should_delete_queue:
            resource.delete()

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

    def create_workers(self, redis_name, workload, workload_args, start_replicas):
        with open(K8S_DIR / "2_worker.yaml") as f:
            # workers, frac_worker = list(yaml.load_all(f, Loader=yaml.FullLoader))
            [workers] = list(yaml.load_all(f, Loader=yaml.FullLoader))
        envvars = [
            {"name": "MANTIS_REDIS_IP", "value": redis_name},
            {"name": "MANTIS_WORKLOAD", "value": workload},
            {"name": "MANTIS_CUSTOM_ARGS", "value": workload_args},
        ]
        workers["spec"]["template"]["spec"]["containers"][0]["env"] = envvars
        workers["spec"]["replicas"] = start_replicas
        # frac_worker["spec"]["containers"][0]["env"] = envvars
        # frac_worker["metadata"]["name"] += "-" + random_letters()

        self.recreate_resource(pykube.Deployment, workers)
        # self.recreate_resource(pykube.Pod, frac_worker)

        def worker_states():
            worker_pods = list(
                pykube.Pod.objects(self.k8s_api).filter(selector={"app": "worker"})
            )
            # worker_pods.append(
            #     pykube.Pod.objects(self.k8s_api).get_by_name(
            #         frac_worker["metadata"]["name"]
            #     )
            # )
            states = {pod.name: pod.ready for pod in worker_pods}
            return states

        states = worker_states()
        while not all(states.values()):
            logger.msg(
                f"Waiting for all worker to become ready: {Counter(states.values()).most_common()}"
            )
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


class ResultWriter:
    def __init__(self, config):
        base = "/{}-{}-{}/{}".format(
            config["load"].replace("/data/", "").replace(".npy", ""),
            config["workload"],
            config["controller"],
            datetime.now().strftime("%m-%d-%H-%M-%S"),
        )
        os.makedirs(base)
        self.base = base

        self.config_path = base + "/config.json"
        self.query_trace_path = base + "/trace.jsonl"
        self.mantis_status_path = base + "/status.jsonl"

        self.trace_file = open(self.query_trace_path, "w")
        self.status_file = open(self.mantis_status_path, "w")

        with open(self.config_path, "w") as f:
            json.dump(config, f)
        self.config = config

    def write_trace_raw(self, msg):
        self.trace_file.write(msg)
        self.trace_file.write("\n")

    def write_summary_dict(self, data):
        self.status_file.write(json.dumps(data))
        self.status_file.write("\n")

    def flush(self):
        self.trace_file.flush()
        self.status_file.flush()

    def experiment_done(self, result=dict()):
        self.run_notebook_script()
        self.upload(result)
        self.post_result(result)

    def upload(self, result=None):
        if result:
            with open(f"{self.base}/result.json", "w") as f:
                json.dump(result, f)

        s3_client = boto3.Session().client("s3")
        for path in glob.glob(f"{self.base}/*"):
            if path.endswith("/"):
                continue
            s3_client.upload_file(
                Filename=path,
                Bucket="mantis-osdi-2020",
                Key=path[1:],
                ExtraArgs={"ACL": "public-read"},
            )
        print("Upload completed!")

    def run_notebook_script(self):
        nb_path = Path(__file__).parent / "plot_mantis.ipynb"
        pm.execute_notebook(
            str(nb_path),
            self.base + "/plot_mantis.ipynb",
            parameters=dict(result_dir=self.base),
        )

    def post_result(self, result=dict()):
        image_base_url = (
            "https://mantis-osdi-2020.s3-us-west-2.amazonaws.com" + self.base
        )
        images = {
            "Latency CDF": image_base_url + "/latency_cdf.png",
            "Controller Actions": image_base_url + "/actions.png",
        }
        text = f"""
Experiment `{self.base}` done:
```
{pformat(self.config)}
```
Result:
```
{pformat(result)}
```
        """
        post_result_to_slack(text, images)



@click.command()
@click.option("--load", required=True, type=click.Path(exists=True))
@click.option("--workload", required=True, type=click.Choice(list(catalogs.keys())))
@click.option("--workload-args", default="", type=str)
@click.option("--controller", required=True, type=click.Choice(list(registry.keys())))
@click.option("--controller-args", default="", type=str)
@click.option("--max-replicas", type=int, default=72)
@click.option("--start-replicas", type=int, default=5)
@click.option("--controller-time-step", type=float, default=5)
# @click.option("--fractional-sleep", type=float, required=True)
def run_controller(
    load,
    workload,
    controller,
    workload_args,
    controller_args,
    max_replicas,
    start_replicas,
    controller_time_step,
    # fractional_sleep,
):
    client = K8sClient()
    ctl = registry[controller](**parse_custom_args(controller_args))

    logger.msg("Creating redis")
    redis_ip = client.create_redis()

    r = redis.Redis(redis_ip, port=7000, decode_responses=True)
    # r.set("fractional_sleep", str(fractional_sleep))
    # r.set("fractional_prob", str(0.5))

    logger.msg("Creating workers")
    client.create_workers(
        redis_ip,
        workload=workload,
        workload_args=workload_args,
        start_replicas=start_replicas,
    )

    logger.msg("Creating load generator")
    num_queries_total, num_queries_received = len(np.load(load)), 0
    client.create_load_generator(redis_ip, workload=workload, load_file=load)

    # Retrieve all parameters
    _local_vars = locals()
    config = {
        v: _local_vars[v] for v in inspect.signature(run_controller.callback).parameters
    }

    # Let workers starts
    r.set("worker_should_go", "true")

    def get_num_replica_registered():
        return len(json.loads(r.execute_command("mantis.status"))["queue_sizes"])

    replica_regstered = 0
    while replica_regstered != start_replicas:
        logger.msg(
            "Waiting for replicas to register", replica_regstered=replica_regstered
        )
        replica_regstered = get_num_replica_registered()
        time.sleep(1)

    # Let load gen start
    r.set("load_gen_should_go", "true")

    writer = ResultWriter(config)

    def scale(new_reps):
        # Set integer component
        client.scale_workers(new_reps)
        # Set fracitonal component
        # frac_val = str(new_reps % 1.0)
        # r.set("fractional_prob", frac_val)
        # logger.msg(f"Setting fractional_value={frac_val}")

    # Stop after stop_condition_count_down * timestep after receiving 100% of the queries
    stop_condition_count_down = 3

    while True:
        start = time.time()

        # Latency list
        length_to_pop = r.llen(RESULT_KEY)
        num_queries_received += length_to_pop

        logger.msg(
            "Result received: {:.2f}%".format(
                num_queries_received * 100 / num_queries_total
            ),
            received=num_queries_received,
            total=num_queries_total,
        )

        e2e_latencies = []
        for _ in range(length_to_pop):
            __, val = r.blpop(RESULT_KEY)
            writer.write_trace_raw(val)
            parsed_msg = json.loads(val)
            query_id = parsed_msg["query_id"]
            e2e_latency = float(parsed_msg["_4_done_time"]) - (parsed_msg["_1_lg_sent"])
            e2e_latencies.append(e2e_latency)
        if len(e2e_latencies):
            percentiles = [25, 50, 95, 99, 100]
            logger.msg(
                "Received {} from last interval".format(len(e2e_latencies)),
                **OrderedDict(
                    zip(
                        map(str, percentiles), np.percentile(e2e_latencies, percentiles)
                    )
                ),
            )
        else:
            logger.msg("No result received in 5sec")

        val = r.execute_command("mantis.status")

        msg = json.loads(val)

        # Msg schema
        # // Real deltas from last call. List[int]
        # status_report["real_arrival_ts_ns"] = timestamps_ns;
        # // Active queue sizes ActiveList[int]
        # status_report["queue_sizes"] = queue_sizes;
        # // Dropped queue sizes DropList[int] (Scaling down)
        # status_report["dropped_queue_sizes"] = dropped_queue_sizes;
        # // -------------------------------------
        # status_report["current_ts_ns"] = current_time;
        # // Float, configurable
        # status_report["fractional_value"] = fractional_val
        # // Queue added/droppede event List[json]
        # status_report["queue_events"] = events;
        #   event["time_ns"] = curr_time_ns; event["type"] = ADD/DROP; event["queue_id"] = queue_name;

        curr_int_reps = len(msg["queue_sizes"])
        # fractional_value = msg["fractional_value"]
        curr_reps = curr_int_reps

        action = ctl.get_action_from_state(
            np.array(e2e_latencies) * 1000,
            np.array(msg["real_arrival_ts_ns"]) / 1000,
            curr_reps,
            sum(msg["queue_sizes"]),
        )
        if action != DONT_SCALE:
            target_reps = curr_reps + action
            target_reps = max(target_reps, 1)
            target_reps = min(target_reps, max_replicas)
            # PID adjustment
            if action > 0:
                target_reps = math.ceil(target_reps)  # Round up
            if action < 0:
                target_reps = math.floor(target_reps)  # Round down
            logger.msg("Scaling to", from_=curr_reps, to_=target_reps, delta=action)
            msg["ctl_from"] = curr_reps
            msg["ctl_action"] = action
            msg["ctl_final_decision"] = target_reps

            scale(target_reps)
        else:
            msg["ctl_from"] = curr_reps
            msg["ctl_action"] = 0
            msg["ctl_final_decision"] = curr_reps
            logger.msg(f"Controller returned {DONT_SCALE}, skipping scaling")

        writer.write_summary_dict(msg)
        writer.flush()

        ## TODO: if queries not equal, wait for few cycles
        finished_percent = int((num_queries_received / num_queries_total) * 100)
        if finished_percent == 100:
            stop_condition_count_down -= 1

        if stop_condition_count_down <= 0:
            logger.msg("All queries received, exitting...")
            client.delete_all_resource()
            result = {
                "num_queries_received": num_queries_received,
                "num_queries_total": num_queries_total,
            }
            writer.experiment_done(result)
            break

        # Make sure ctl interval is 5s
        compute_duration = time.time() - start
        should_sleep = controller_time_step - compute_duration
        should_sleep = 0 if should_sleep < 0 else should_sleep
        logger.msg(f"Sleeping for {should_sleep:.2f} s")
        time.sleep(should_sleep)
