from controllers import BangBang, PID


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


def test_pid():
    pid = PID()

    no_action = pid.get_action_from_state([], [], 0, 0)

