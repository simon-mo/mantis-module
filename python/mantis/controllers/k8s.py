import pykube
import yaml
from structlog import get_logger

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
