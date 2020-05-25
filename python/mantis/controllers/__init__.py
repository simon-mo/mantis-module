from mantis.controllers.bangbang import BangBang
from mantis.controllers.debug import (
    FixedActionController,
    RandomAddAndDelete,
    AddDeleteFixed,
    Scheduled,
)
from mantis.controllers.pid import PIDController
from mantis.controllers.k8s import K8sNative, DONT_SCALE

registry = {
    "pid": PIDController,
    "bangbang": BangBang,
    "fixed": FixedActionController,
    "random": RandomAddAndDelete,
    "add_delete_fixed": AddDeleteFixed,
    "k8s_native": K8sNative,
    "scheduled": Scheduled,
}
