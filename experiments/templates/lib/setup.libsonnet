{
    "default": [
        "--start-replicas", "10",
        "--controller-time-step", "5"
    ],
    make_spin_up_time_config(time_step):: [
        "--start-replicas", "1",
        "--controller-time-step", std.toString(time_step)
    ]
}