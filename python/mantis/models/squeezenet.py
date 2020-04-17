import numpy as np
import torch
from torchvision.models import squeezenet1_1
import base64

SHAPES = (1, 3, 224, 224)


class Squeezenet:
    def __init__(self):
        self.model = squeezenet1_1(pretrained=True)

    def __call__(self, payload):
        # 31.4 ms ± 2.55 ms per loop (mean ± std. dev. of 7 runs, 10 loops each)
        # 1s / 40ms -> 25 qps, to reach 1000 qps, needs 40 cores
        decoded = base64.b64decode(payload)
        arr = np.frombuffer(decoded, dtype="float32").reshape(*SHAPES)
        with torch.no_grad():
            pred = self.model(torch.tensor(arr))
        pred_bytes = pred.detach().numpy().tobytes()
        pred_str = base64.b64encode(pred_bytes)
        return pred_str

    @staticmethod
    def generate_workload():
        payload = np.zeros(SHAPES, dtype="float32").tobytes()
        return base64.b64encode(payload)
