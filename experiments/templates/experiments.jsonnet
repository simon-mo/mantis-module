local base = import 'lib/base.libsonnet';
local controllers = import 'lib/controllers.libsonnet';
local workloads = import 'lib/workloads.libsonnet';
local loads = import 'lib/loads.libsonnet';
local setup = import 'lib/setup.libsonnet';


local make_experiment(ctl,workload,load,setup) =
    local name = std.join("-", ["controller", ctl, workload, load, setup[3]]);
    local cmdline = controllers[ctl] + workloads[workload] + loads[load] + setup;
    [name+".json", base.config(name=name, cmdline=cmdline)];

local experiments = [
  make_experiment(
    "scheduled-override",
    "busy-sleep-20ms",
    "three-min",
    setup.make_spin_up_time_config(time_step=ts))
  for ts in [1,2,5]
] + [
  make_experiment(
    "fixed-adder-1",
    wkld,
    "three-min",
    setup.make_spin_up_time_config(time_step=ts)
  ) for wkld in ["busy-sleep-20ms", "nlp", "vision"]
    for ts in [1,5, 10]
];

{
  // 'out.json':
  //   base.config(name='hi', cmdline=controllers["fixed-adder-1"]),
  [a[0]]: a[1] for a in experiments
}
