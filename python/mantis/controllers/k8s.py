import pykube
import time
import yaml
from structlog import get_logger
from subprocess import Popen
import requests
from typing import Dict

from mantis.controllers.base import BaseController


#: Constant telling the runner don't apply any scaling action
DONT_SCALE = "DONT_SCALE"

raw_config = """
apiVersion: autoscaling/v1
kind: HorizontalPodAutoscaler
metadata:
    name: mantis-worker
    namespace: default
spec:
    scaleTargetRef:
        apiVersion: apps/v1
        kind: Deployment
        name: mantis-worker
    minReplicas: {min_replica}
    maxReplicas: {max_replica}
    targetCPUUtilizationPercentage: {percentage}
"""

logger = get_logger()


class K8sNative:
    def __init__(self, target_cpu, max_replicas):
        target_cpu = int(target_cpu)
        assert 0 < target_cpu < 100

        config = yaml.safe_load(
            raw_config.format(
                min_replica=1, max_replica=int(max_replicas), percentage=int(target_cpu)
            )
        )
        client = pykube.HTTPClient(pykube.KubeConfig.from_env())
        spec = pykube.HorizontalPodAutoscaler(client, config)
        spec.delete()
        spec.create()
        logger.msg("Created K8sNative autoscaler")

    def get_action_from_state(self, lats, deltas, num_replicas, qlen):
        return DONT_SCALE


# NotImplemented/WIP: not prioritized right now
class K8sPython(BaseController):
    def __init__(self, target_cpu, max_replicas):
        target_cpu = int(target_cpu)
        assert 0 < target_cpu < 100

        self._run_proxy()
        time.sleep(1)
        self.get_metrics_from_k8s()

    def _run_proxy(self):
        self.proxy_proc = Popen(["kubectl", "proxy", "--port=8099"])
        self.metric_url = "http://localhost:8099/apis/metrics.k8s.io/v1beta1/pods"

        logger.msg("Kube proxy success")

    def get_metrics_from_k8s(self) -> Dict[str, float]:
        resp = requests.get(self.metric_url)
        assert resp.status_code == 200, resp.text

        data = resp.json()

        # Schema:
        # {
        #     "apiVersion": "metrics.k8s.io/v1beta1",
        #     "items": [
        #         ...
        #         {
        #             "containers": [
        #                 {
        #                     "name": "worker",
        #                     "usage": {
        #                         "cpu": "351154086n",
        #                         "memory": "116080Ki"
        #                     }
        #                 }
        #             ],
        #             "metadata": {
        #                 "creationTimestamp": "2020-05-08T21:44:57Z",
        #                 "name": "mantis-worker-86c846977f-ph8zj",
        #                 "namespace": "default",
        #                 "selfLink": "/apis/metrics.k8s.io/v1beta1/namespaces/default/pods/mantis-worker-86c846977f-ph8zj"
        #             },
        #             "timestamp": "2020-05-08T21:44:41Z",
        #             "window": "30s"
        #         },
        metric_items = data["items"]
        pod_name_to_cpus = dict()
        for item in metric_items:
            # Find the pod name
            name = item["metadata"]["name"]
            if "mantis-worker" not in name:
                continue
            # Find the cpu fraction
            containers = item["containers"]
            cpu_usage_s = [c for c in containers if c["name"] == "worker"][0]["usage"][
                "cpu"
            ]
            assert cpu_usage_s.endswith("n")
            cpu_usage_core = int(cpu_usage_s[:-1]) / 1e9
            # Add to dictionary
            pod_name_to_cpus[name] = cpu_usage_core

        return pod_name_to_cpus

    def get_action_from_state(self, *discard_args, **discard_kwargs):
        pods_to_cpus = self.get_metrics_from_k8s()

        # https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/#algorithm-details

        # From the most basic perspective, the Horizontal Pod Autoscaler controller operates
        # on the ratio between desired metric value and current metric value:
        # desiredReplicas = ceil[currentReplicas * ( currentMetricValue / desiredMetricValue )]
        # For example, if the current metric value is 200m, and the desired value is 100m, the
        # number of replicas will be doubled, since 200.0 / 100.0 == 2.0 If the current
        # value is instead 50m, we’ll halve the number of replicas, since 50.0 / 100.0 == 0.5.
        # We’ll skip scaling if the ratio is sufficiently close to 1.0 (within a
        # globally-configurable tolerance, from the --horizontal-pod-autoscaler-tolerance
        # flag, which defaults to 0.1).

        # ratio = curr

        # When a targetAverageValue or targetAverageUtilization is specified, the currentMetricValue is
        # computed by taking the average of the given metric across all Pods in the
        # HorizontalPodAutoscaler’s scale target. Before checking the tolerance and
        # deciding on the final values, we take pod readiness and missing metrics into
        # consideration, however.

        # All Pods with a deletion timestamp set (i.e. Pods in the process of being shut down)
        # and all failed Pods are discarded.

        # If a particular Pod is missing metrics, it is set aside for later; Pods with missing
        # metrics will be used to adjust the final scaling amount.

        # When scaling on CPU, if any pod has yet to become ready (i.e. it’s still initializing)
        # or the most recent metric point for the pod was before it became ready, that pod is set
        # aside as well.

        # Due to technical constraints, the HorizontalPodAutoscaler controller cannot exactly
        # determine the first time a pod becomes ready when determining whether to set aside
        # certain CPU metrics. Instead, it considers a Pod “not yet ready” if it’s unready and
        # transitioned to unready within a short, configurable window of time since it started. This
        # value is configured with the --horizontal-pod-autoscaler-initial-readiness-delay flag,
        # and its default is 30 seconds. Once a pod has become ready, it considers any transition
        # to ready to be the first if it occurred within a longer, configurable time since it started.
        # This value is configured with the --horizontal-pod-autoscaler-cpu-initialization-period flag,
        # and its default is 5 minutes.

        # The currentMetricValue / desiredMetricValue base scale ratio is then calculated using
        # the remaining pods not set aside or discarded from above.

        # If there were any missing metrics, we recompute the average more conservatively, assuming
        # those pods were consuming 100% of the desired value in case of a scale down, and 0% in case
        # of a scale up. This dampens the magnitude of any potential scale.

        # Furthermore, if any not-yet-ready pods were present, and we would have scaled up without
        # factoring in missing metrics or not-yet-ready pods, we conservatively assume the not-yet-ready
        # pods are consuming 0% of the desired metric, further dampening the magnitude of a scale up.

        # After factoring in the not-yet-ready pods and missing metrics, we recalculate the usage
        # ratio. If the new ratio reverses the scale direction, or is within the tolerance, we skip
        # scaling. Otherwise, we use the new ratio to scale.

        # Note that the original value for the average utilization is reported back via the
        # HorizontalPodAutoscaler status, without factoring in the not-yet-ready pods or missing
        # metrics, even when the new usage ratio is used.

        # If multiple metrics are specified in a HorizontalPodAutoscaler, this calculation is done
        # for each metric, and then the largest of the desired replica counts is chosen. If any of
        # these metrics cannot be converted into a desired replica count (e.g. due to an error fetching
        # the metrics from the metrics APIs) and a scale down is suggested by the metrics which can be
        # fetched, scaling is skipped. This means that the HPA is still capable of scaling up if one or
        # more metrics give a desiredReplicas greater than the current value.

        # Finally, just before HPA scales the target, the scale recommendation is recorded. The
        # controller considers all recommendations within a configurable window choosing the
        # highest recommendation from within that window. This value can be configured using
        # the --horizontal-pod-autoscaler-downscale-stabilization flag, which defaults to 5
        # minutes. This means that scaledowns will occur gradually, smoothing out the impact of rapidly
        # fluctuating metric values.
