import numpy as np

from mantis.controllers.base import BaseController


class BangBang:
    slo = 150  # ms
    low = 0.5 * slo
    high = 0.8 * slo

    def get_action_from_state(self, lats, deltas, num_replicas, qlen):
        if len(lats) == 0:
            return 0
        p99 = np.percentile(lats, 99)
        if p99 < self.low:
            return -0.8
        if p99 > self.high:
            return 0.8
        return 0


def test_bang_bang():
    b = BangBang()

    no_data = b.get_action_from_state([], [], 0, 0)
    assert no_data == 0

    high_watermark = b.high
    should_increase = b.get_action_from_state(
        lats=[high_watermark * 10 for _ in range(10)], deltas=[], num_replicas=0, qlen=0
    )
    assert should_increase == 0.8

    low_watermark = b.low
    should_decrease = b.get_action_from_state(
        lats=[low_watermark * 0.5 for _ in range(10)], deltas=[], num_replicas=0, qlen=0
    )
    assert should_decrease == -0.8
